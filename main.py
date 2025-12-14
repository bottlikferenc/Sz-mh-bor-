from __future__ import annotations
import random
from dataclasses import dataclass

from kivy.app import App
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.popup import Popup

# PC teszthez (mobilon figyelmen kívül marad)
Window.size = (980, 720)

GAME_TITLE = "Számos Sakk"
BOARD_N = 10
TURN_SECONDS = 5 * 60  # 5 perc / játékos


def mmss(seconds: float) -> str:
    s = max(0, int(seconds))
    return f"{s//60:02d}:{s%60:02d}"


def popup(title: str, msg: str, on_ok=None):
    box = BoxLayout(orientation="vertical", padding=12, spacing=10)
    box.add_widget(Label(text=msg, font_size="14sp"))
    btn = Button(text="OK", size_hint=(1, None), height=44)
    box.add_widget(btn)
    pop = Popup(title=title, content=box, size_hint=(None, None), size=(620, 340))

    def _close(*_):
        pop.dismiss()
        if on_ok:
            on_ok()

    btn.bind(on_release=_close)
    pop.open()


@dataclass
class GameResult:
    winner: str  # "Fehér" / "Fekete" / "Döntetlen"
    white_left: int
    black_left: int
    white_sum: int
    black_sum: int
    reason: str  # "Idő" / "Elfogyott" / stb.


class MenuScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        root = BoxLayout(orientation="vertical", padding=20, spacing=14)

        title = Label(text=GAME_TITLE, font_size="32sp", bold=True)
        subtitle = Label(text=f"{BOARD_N}×{BOARD_N} – kattintásos, 2 játékos (hot-seat)", font_size="18sp")

        btn_start = Button(text="Játék indítása", size_hint=(1, None), height=60)
        btn_stats = Button(text="Statisztika", size_hint=(1, None), height=54)
        btn_exit = Button(text="Kilépés", size_hint=(1, None), height=54)

        btn_start.bind(on_release=lambda *_: self.manager.get_screen("game").start_new_game())
        btn_stats.bind(on_release=lambda *_: setattr(self.manager, "current", "stats"))
        btn_exit.bind(on_release=lambda *_: App.get_running_app().stop())

        rules = Label(
            text=(
                "[b]Új játékszabály[/b]\n"
                "• Minden játék elején 100 db [b]különböző[/b] szám kerül a táblára 1–128 között (nincs ismétlődés a táblán).\n"
                "• Kezdés: véletlenszerű (Fehér vagy Fekete).\n"
                "• Ütés: jelölj ki 1 ellenséget (CÉL) + saját bábukat (TÁMADÓK, vegyesen is). "
                "Ha a támadók összege = cél, akkor eltűnik a cél + az összes támadó.\n"
                "• Idő: 5 perc / játékos. Időnél: több bábu nyer; ha egyenlő → összérték; ha az is → döntetlen."
            ),
            markup=True,
            font_size="14sp",
        )

        root.add_widget(Label(size_hint=(1, 0.10)))
        root.add_widget(title)
        root.add_widget(subtitle)
        root.add_widget(Label(size_hint=(1, 0.05)))
        root.add_widget(btn_start)
        root.add_widget(btn_stats)
        root.add_widget(Label(size_hint=(1, 0.05)))
        root.add_widget(rules)
        root.add_widget(Label(size_hint=(1, 0.05)))
        root.add_widget(btn_exit)

        self.add_widget(root)


class StatsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        root = BoxLayout(orientation="vertical", padding=16, spacing=12)

        self.lbl_title = Label(text="[b]Statisztika[/b]", markup=True, font_size="26sp", size_hint=(1, None), height=50)
        self.lbl_body = Label(text="", font_size="15sp")
        btn_back = Button(text="Vissza a menübe", size_hint=(1, None), height=54)
        btn_reset = Button(text="Statisztika nullázása", size_hint=(1, None), height=54)

        btn_back.bind(on_release=lambda *_: setattr(self.manager, "current", "menu"))
        btn_reset.bind(on_release=lambda *_: App.get_running_app().reset_stats())

        root.add_widget(self.lbl_title)
        root.add_widget(self.lbl_body)
        root.add_widget(btn_reset)
        root.add_widget(btn_back)
        self.add_widget(root)

    def on_pre_enter(self, *args):
        app = App.get_running_app()
        self.lbl_body.text = app.format_stats()


class Cell(Button):
    def __init__(self, row: int, col: int, **kwargs):
        super().__init__(**kwargs)
        self.row = row
        self.col = col
        self.owner: str | None = None   # "Fehér" / "Fekete" / None
        self.value: int | None = None

        self.base_bg = (1, 1, 1, 1)
        self.background_normal = ""
        self.color = (0, 1, 0, 1)  # zöld szám

        self.is_target = False
        self.is_attacker = False


class GameScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.current_player = "Fehér"
        self.time_left = {"Fehér": TURN_SECONDS, "Fekete": TURN_SECONDS}
        self.paused = False
        self._tick_event = None

        self.target_pos: tuple[int, int] | None = None
        self.attackers: set[tuple[int, int]] = set()

        root = BoxLayout(orientation="vertical", padding=10, spacing=8)

        # ===== HUD (2 sor) =====
        hud = BoxLayout(orientation="vertical", size_hint=(1, None), height=92, spacing=6, padding=(4, 4))
        row1 = BoxLayout(orientation="horizontal", size_hint=(1, None), height=44, spacing=8)

        self.lbl_turn = Label(text="Soron: -", font_size="18sp", size_hint=(0.22, 1))
        self.lbl_time = Label(text=self._time_text(), font_size="18sp", size_hint=(0.44, 1))
        self.lbl_state = Label(text="Cél: - | Összeg: 0", font_size="18sp", size_hint=(0.34, 1))

        row1.add_widget(self.lbl_turn)
        row1.add_widget(self.lbl_time)
        row1.add_widget(self.lbl_state)

        row2 = BoxLayout(orientation="horizontal", size_hint=(1, None), height=42, spacing=8)
        btn_pass = Button(text="Kör vége", size_hint=(0.20, 1))
        btn_clear = Button(text="Törlés", size_hint=(0.16, 1))
        self.btn_pause = Button(text="Szünet", size_hint=(0.16, 1))
        btn_new = Button(text="Új játék", size_hint=(0.18, 1))
        btn_menu = Button(text="Menü", size_hint=(0.12, 1))
        btn_stats = Button(text="Statisztika", size_hint=(0.18, 1))

        btn_pass.bind(on_release=lambda *_: self.pass_turn())
        btn_clear.bind(on_release=lambda *_: self.clear_selections("Kijelölések törölve."))
        self.btn_pause.bind(on_release=lambda *_: self.toggle_pause())
        btn_new.bind(on_release=lambda *_: self.start_new_game())
        btn_menu.bind(on_release=lambda *_: setattr(self.manager, "current", "menu"))
        btn_stats.bind(on_release=lambda *_: setattr(self.manager, "current", "stats"))

        row2.add_widget(btn_pass)
        row2.add_widget(btn_clear)
        row2.add_widget(self.btn_pause)
        row2.add_widget(btn_new)
        row2.add_widget(btn_stats)
        row2.add_widget(btn_menu)

        hud.add_widget(row1)
        hud.add_widget(row2)

        # ===== BOARD =====
        self.grid = GridLayout(cols=BOARD_N, rows=BOARD_N, spacing=2, size_hint=(1, 1))
        self.cells: dict[tuple[int, int], Cell] = {}

        for r in range(BOARD_N):
            for c in range(BOARD_N):
                cell = Cell(r, c, text="", font_size="16sp")
                light = (0.94, 0.85, 0.72, 1)
                dark = (0.70, 0.52, 0.38, 1)
                cell.base_bg = light if (r + c) % 2 == 0 else dark
                cell.background_color = cell.base_bg
                cell.bind(on_release=self.on_cell_click)
                self.cells[(r, c)] = cell
                self.grid.add_widget(cell)

        self.lbl_info = Label(
            text="1) CÉL: ellenségre katt. 2) TÁMADÓK: sajátokra katt (vegyesen is). Ha összeg=cél → ütés.",
            font_size="14sp",
            size_hint=(1, None),
            height=44,
        )

        root.add_widget(hud)
        root.add_widget(self.grid)
        root.add_widget(self.lbl_info)
        self.add_widget(root)

    # ---------- lifecycle / timer ----------
    def on_enter(self, *args):
        if self._tick_event is None:
            self._tick_event = Clock.schedule_interval(self._tick, 1)

    def on_leave(self, *args):
        if self._tick_event is not None:
            self._tick_event.cancel()
            self._tick_event = None

    def _tick(self, dt):
        if self.paused:
            return
        self.time_left[self.current_player] -= 1
        if self.time_left[self.current_player] <= 0:
            self.time_left[self.current_player] = 0
            self.finish_game(reason="Idő")
            return
        self.update_hud()

    # ---------- new game ----------
    def start_new_game(self):
        # random kezdés
        self.current_player = random.choice(["Fehér", "Fekete"])
        self.time_left = {"Fehér": TURN_SECONDS, "Fekete": TURN_SECONDS}
        self.paused = False
        self._clear_all_selections()

        # ÚJ JÁTÉKSZABÁLY: 100 különböző szám 1..128 között
        numbers = random.sample(range(1, 129), BOARD_N * BOARD_N)  # 100 db unique
        # felosztás: felső 50 fekete, alsó 50 fehér
        black_nums = numbers[:50]
        white_nums = numbers[50:]

        # táblát kitöltjük
        # felső 5 sor = fekete
        bi = 0
        wi = 0
        for r in range(BOARD_N):
            for c in range(BOARD_N):
                cell = self.cells[(r, c)]
                cell.is_target = False
                cell.is_attacker = False

                if r < BOARD_N // 2:
                    val = black_nums[bi]
                    bi += 1
                    self._set_piece(cell, "Fekete", val)
                else:
                    val = white_nums[wi]
                    wi += 1
                    self._set_piece(cell, "Fehér", val)

        self.lbl_info.text = f"Új játék! Kezd: {self.current_player}. (Minden szám egyedi 1–128 között.)"
        self.update_hud()

        # timer biztosan menjen
        if self._tick_event is None:
            self._tick_event = Clock.schedule_interval(self._tick, 1)

        self.manager.current = "game"

    def _set_piece(self, cell: Cell, owner: str, value: int):
        cell.owner = owner
        cell.value = int(value)
        cell.text = str(int(value))
        # bábu szín (egyszerű, mobilbarát)
        cell.background_color = (0.95, 0.95, 0.95, 1) if owner == "Fehér" else (0.18, 0.18, 0.18, 1)
        cell.color = (0, 1, 0, 1)

    # ---------- UI helpers ----------
    def _time_text(self):
        return f"Idő – F: {mmss(self.time_left['Fehér'])} | B: {mmss(self.time_left['Fekete'])}"

    def update_hud(self):
        target_val = "-"
        if self.target_pos is not None:
            t = self.cells[self.target_pos]
            if t.value is not None:
                target_val = str(t.value)

        s = self.attack_sum()
        self.lbl_turn.text = f"Soron: {self.current_player}"
        self.lbl_time.text = self._time_text()
        self.lbl_state.text = f"Cél: {target_val} | Összeg: {s}"
        self.btn_pause.text = "Folytat" if self.paused else "Szünet"

    def toggle_pause(self):
        self.paused = not self.paused
        self.update_hud()
        self.lbl_info.text = "SZÜNET" if self.paused else "Folytatás."

    def pass_turn(self):
        self._clear_all_selections()
        self.current_player = "Fekete" if self.current_player == "Fehér" else "Fehér"
        self.lbl_info.text = "Kör átadva."
        self.update_hud()

    def clear_selections(self, msg="Kijelölések törölve."):
        self._clear_all_selections()
        self.lbl_info.text = msg
        self.update_hud()

    # ---------- click logic ----------
    def on_cell_click(self, cell: Cell):
        if self.paused:
            self.lbl_info.text = "Szünet van. Nyomd meg a Folytat gombot."
            return

        if cell.owner is None:
            self.clear_selections("Üres mező – kijelölések törölve.")
            return

        enemy = "Fekete" if self.current_player == "Fehér" else "Fehér"
        pos = (cell.row, cell.col)

        # cél: ellenség
        if cell.owner == enemy:
            # toggle target
            if self.target_pos == pos:
                self._unselect_target(pos)
                self.target_pos = None
                self.lbl_info.text = "Cél kijelölés törölve."
            else:
                if self.target_pos is not None:
                    self._unselect_target(self.target_pos)
                self.target_pos = pos
                self._select_target(pos)
                self.lbl_info.text = f"Cél kijelölve: {cell.owner} {cell.value}"

            self.try_capture()
            self.update_hud()
            return

        # támadók: saját
        if cell.owner == self.current_player:
            if pos in self.attackers:
                self.attackers.remove(pos)
                self._unselect_attacker(pos)
            else:
                self.attackers.add(pos)
                self._select_attacker(pos)

            self.try_capture()
            self.update_hud()
            return

    def attack_sum(self) -> int:
        s = 0
        for pos in self.attackers:
            c = self.cells[pos]
            if c.owner == self.current_player and c.value is not None:
                s += int(c.value)
        return s

    def try_capture(self):
        if self.target_pos is None or not self.attackers:
            return

        target = self.cells[self.target_pos]
        if target.value is None:
            return

        goal = int(target.value)
        s = self.attack_sum()

        # csak tényt mutatunk
        self.lbl_info.text = f"Cél={goal} | Összeg={s}"

        if s != goal:
            return

        # ÜTÉS: cél + támadók eltűnnek
        self._remove_piece(self.target_pos)
        self.target_pos = None

        for pos in list(self.attackers):
            self._remove_piece(pos)
        self.attackers.clear()

        self.lbl_info.text = "KIÜTÉS! Cél + támadók eltűntek. Kör váltás."

        # game over check
        if self.is_game_over_by_empty():
            self.finish_game(reason="Elfogyott")
            return

        self._clear_all_selections()
        self.current_player = "Fekete" if self.current_player == "Fehér" else "Fehér"
        self.update_hud()

    # ---------- selection visuals ----------
    def _select_target(self, pos):
        c = self.cells[pos]
        c.is_target = True
        c.background_color = (0.78, 0.22, 0.22, 1)

    def _unselect_target(self, pos):
        c = self.cells[pos]
        c.is_target = False
        self._restore_piece_color(c)

    def _select_attacker(self, pos):
        c = self.cells[pos]
        c.is_attacker = True
        c.background_color = (0.25, 0.65, 0.25, 1)

    def _unselect_attacker(self, pos):
        c = self.cells[pos]
        c.is_attacker = False
        self._restore_piece_color(c)

    def _restore_piece_color(self, c: Cell):
        if c.owner is None:
            c.background_color = c.base_bg
        else:
            c.background_color = (0.95, 0.95, 0.95, 1) if c.owner == "Fehér" else (0.18, 0.18, 0.18, 1)

    def _clear_all_selections(self):
        if self.target_pos is not None:
            self._unselect_target(self.target_pos)
        self.target_pos = None

        for pos in list(self.attackers):
            self._unselect_attacker(pos)
        self.attackers.clear()

    def _remove_piece(self, pos):
        c = self.cells[pos]
        c.owner = None
        c.value = None
        c.text = ""
        c.is_target = False
        c.is_attacker = False
        c.background_color = c.base_bg

    # ---------- win / stats ----------
    def count_pieces(self, owner: str) -> int:
        return sum(1 for c in self.cells.values() if c.owner == owner and c.value is not None)

    def sum_values(self, owner: str) -> int:
        return sum(int(c.value) for c in self.cells.values() if c.owner == owner and c.value is not None)

    def is_game_over_by_empty(self) -> bool:
        w = self.count_pieces("Fehér")
        b = self.count_pieces("Fekete")
        return (w == 0) or (b == 0)

    def finish_game(self, reason: str):
        # megállítjuk az órát
        if self._tick_event is not None:
            self._tick_event.cancel()
            self._tick_event = None

        w_cnt = self.count_pieces("Fehér")
        b_cnt = self.count_pieces("Fekete")
        w_sum = self.sum_values("Fehér")
        b_sum = self.sum_values("Fekete")

        # Győztes logika (időnél is ez)
        if w_cnt != b_cnt:
            winner = "Fehér" if w_cnt > b_cnt else "Fekete"
        else:
            if w_sum != b_sum:
                winner = "Fehér" if w_sum > b_sum else "Fekete"
            else:
                winner = "Döntetlen"

        result = GameResult(
            winner=winner,
            white_left=w_cnt,
            black_left=b_cnt,
            white_sum=w_sum,
            black_sum=b_sum,
            reason=reason,
        )

        App.get_running_app().record_result(result)

        msg = (
            f"Ok: {reason}\n\n"
            f"Maradt bábuk: Fehér {w_cnt} | Fekete {b_cnt}\n"
            f"Összérték:    Fehér {w_sum} | Fekete {b_sum}\n\n"
            f"Győztes: {winner}"
        )

        def _to_stats():
            self.manager.current = "stats"

        popup("Játék vége", msg, on_ok=_to_stats)


class SzamosSakkApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.results: list[GameResult] = []

    def build(self):
        sm = ScreenManager(transition=FadeTransition(duration=0.2))
        sm.add_widget(MenuScreen(name="menu"))
        sm.add_widget(GameScreen(name="game"))
        sm.add_widget(StatsScreen(name="stats"))
        sm.current = "menu"
        return sm

    # ---- stats ----
    def record_result(self, r: GameResult):
        self.results.append(r)

    def reset_stats(self):
        self.results.clear()

    def format_stats(self) -> str:
        n = len(self.results)
        if n == 0:
            return "Még nincs lejátszott meccs."

        white_wins = sum(1 for r in self.results if r.winner == "Fehér")
        black_wins = sum(1 for r in self.results if r.winner == "Fekete")
        draws = sum(1 for r in self.results if r.winner == "Döntetlen")

        avg_white_left = sum(r.white_left for r in self.results) / n
        avg_black_left = sum(r.black_left for r in self.results) / n

        time_ends = sum(1 for r in self.results if r.reason == "Idő")
        empty_ends = sum(1 for r in self.results if r.reason == "Elfogyott")

        last = self.results[-1]

        return (
            f"Lejátszott meccsek: {n}\n\n"
            f"Fehér győzelmek: {white_wins}\n"
            f"Fekete győzelmek: {black_wins}\n"
            f"Döntetlenek: {draws}\n\n"
            f"Átlag maradék bábuk:\n"
            f"  Fehér: {avg_white_left:.1f}\n"
            f"  Fekete: {avg_black_left:.1f}\n\n"
            f"Befejezés oka:\n"
            f"  Idő: {time_ends}\n"
            f"  Elfogyott: {empty_ends}\n\n"
            f"Utolsó meccs:\n"
            f"  Győztes: {last.winner}\n"
            f"  Maradt: Fehér {last.white_left} | Fekete {last.black_left}\n"
            f"  Összérték: Fehér {last.white_sum} | Fekete {last.black_sum}\n"
            f"  Ok: {last.reason}"
        )


if __name__ == "__main__":
    SzamosSakkApp().run()