import os
import csv
import asyncio
from datetime import datetime
import flet as ft

CSV_FILE = "tasks.csv"


class TaskManagerApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Менеджер Задач"
        self.page.theme_mode = ft.ThemeMode.SYSTEM
        self.page.window_width = 620
        self.page.window_height = 550

        # Базовый отступ
        self.page.padding = 10

        self.tasks = []
        self.load_tasks()

        # Список задач
        self.task_list_view = ft.ListView(expand=True, spacing=4)

        self.sort_dropdown = ft.Dropdown(
            label="Сортировка",
            value="По порядку",
            options=[
                ft.dropdown.Option("По порядку"),
                ft.dropdown.Option("По алфавиту"),
                ft.dropdown.Option("По дедлайну")
            ],
            width=180,
            content_padding=5
        )
        self.sort_dropdown.on_change = self.on_sort_changed

        # Компактная кнопка для верхнего угла
        self.add_button = ft.FloatingActionButton(
            content=ft.Row([ft.Icon(ft.Icons.ADD, size=16), ft.Text("Новая задача", size=11)],
                           alignment=ft.MainAxisAlignment.CENTER),
            on_click=self.open_add_dialog,
            width=130,
            height=34
        )

        top_menu_row = ft.Row([self.sort_dropdown, self.add_button], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        # Безопасная зона для статус-бара телефона
        safe_top_panel = ft.SafeArea(
            content=ft.Container(
                content=top_menu_row,
                margin=ft.Margin(0, 24, 0, 0)
            )
        )

        self.page.add(
            safe_top_panel,
            self.task_list_view
        )

        self.refresh_list()
        asyncio.create_task(self.background_timer())

    def load_tasks(self):
        """Чтение данных по индексам колонок CSV с поддержкой поля Note"""
        self.tasks = []
        if os.path.exists(CSV_FILE):
            with open(CSV_FILE, mode='r', encoding='utf-8') as f:
                reader = csv.reader(f)
                try:
                    next(reader, None)
                except StopIteration:
                    return
                for row in reader:
                    if len(row) >= 3:
                        # Если в файле нет поля заметки (старая база), ставим пустую строку
                        note = row[4].strip() if len(row) >= 5 else ""
                        status = row[3].strip() if len(row) >= 4 else "active"

                        self.tasks.append({
                            "name": row[0].strip(),
                            "date": row[1].strip(),
                            "time": row[2].strip(),
                            "status": status,
                            "note": note
                        })

    def save_tasks(self):
        """Сохранение данных в CSV, включая столбец Note"""
        with open(CSV_FILE, mode='w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Name", "Date", "Time", "Status", "Note"])
            for t in self.tasks:
                writer.writerow([t["name"], t["date"], t["time"], t["status"], t["note"]])

    def check_is_expired(self, date_str, time_str):
        try:
            return datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M") < datetime.now()
        except ValueError:
            return False

    async def background_timer(self):
        while True:
            await asyncio.sleep(10)
            self.refresh_list()

    def on_sort_changed(self, e):
        self.refresh_list()

    def get_sorted_tasks(self):
        indexed_tasks = list(enumerate(self.tasks))
        mode = self.sort_dropdown.value

        if mode == "По дедлайну":
            def parse_dt(item):
                try:
                    return datetime.strptime(f"{item['date']} {item['time']}", "%d.%m.%Y %H:%M")
                except ValueError:
                    return datetime.max

            indexed_tasks.sort(key=parse_dt)
        elif mode == "По алфавиту":
            indexed_tasks.sort(key=lambda item: item["name"].lower())

        return indexed_tasks

    def refresh_list(self):
        self.task_list_view.controls.clear()

        if not self.tasks:
            self.task_list_view.controls.append(ft.Text("Список задач пуст", italic=True, size=13))
            self.page.update()
            return

        for original_index, task in self.get_sorted_tasks():
            is_expired = self.check_is_expired(task['date'], task['time'])

            if task['status'] == "performed":
                color = ft.Colors.GREY_800
                text_color = ft.Colors.GREY_400
                icon_color = ft.Colors.GREY_400
                icon_type = ft.Icons.CHECK_CIRCLE
            elif is_expired:
                color = "#4a0d0d"
                text_color = ft.Colors.WHITE
                icon_color = ft.Colors.RED_400
                icon_type = ft.Icons.ALARM
            else:
                color = ft.Colors.BLUE_GREY_900 if self.page.theme_mode == ft.ThemeMode.DARK else ft.Colors.BLUE_50
                text_color = ft.Colors.WHITE if self.page.theme_mode == ft.ThemeMode.DARK else ft.Colors.BLACK
                icon_color = ft.Colors.BLUE_400
                icon_type = ft.Icons.PUSH_PIN

            # Проверяем, есть ли у задачи скрытая заметка, чтобы добавить визуальный индикатор 📝
            task_display_name = task['name']
            if task.get("note", "").strip():
                task_display_name = f"📝 {task['name']}"

            left_side = ft.Row(
                controls=[
                    ft.Icon(icon_type, size=16, color=icon_color),
                    ft.Container(
                        content=ft.Text(
                            task_display_name,
                            weight=ft.FontWeight.BOLD,
                            size=14,
                            color=text_color,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            max_lines=1
                        ),
                        expand=True
                    ),
                ],
                spacing=8,
                alignment=ft.MainAxisAlignment.START,
                expand=True
            )

            right_side = ft.Row(
                controls=[
                    ft.Text(f"{task['date']} {task['time']}", size=11, color=text_color),
                ],
                spacing=0,
                alignment=ft.MainAxisAlignment.END
            )

            row_content = ft.Row(
                controls=[left_side, right_side],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
            )

            task_container = ft.Container(
                content=row_content,
                bgcolor=color,
                border_radius=4,
                padding=ft.Padding(10, 6, 10, 6),
                on_click=lambda e, idx=original_index: self.open_edit_window(idx)
            )

            self.task_list_view.controls.append(task_container)

        self.page.update()

    def open_add_dialog(self, e):
        self.show_task_dialog("Создать задачу", None)

    def open_edit_window(self, index):
        self.show_task_dialog("Редактировать задачу", index)

    def show_task_dialog(self, title, index=None):
        task = self.tasks[index] if index is not None else None

        name_input = ft.TextField(label="Название задачи", value=task["name"] if task else "", dense=True)

        # Добавляем новое многострочное поле для Заметки (Note)
        note_input = ft.TextField(
            label="Заметка / Описание",
            value=task["note"] if task and "note" in task else "",
            multiline=True,
            min_lines=2,
            max_lines=4,
            hint_text="Введите сюда детали задачи...",
            dense=True
        )

        current_year = datetime.now().year
        days = [f"{i:02d}" for i in range(1, 32)]
        months = [f"{i:02d}" for i in range(1, 13)]
        years = [str(y) for y in range(current_year - 1, current_year + 5)]
        hours = [f"{i:02d}" for i in range(24)]
        minutes = [f"{i:02d}" for i in range(60)]

        now = datetime.now()
        d_day, d_mon, d_yr = f"{now.day:02d}", f"{now.month:02d}", str(now.year)
        t_h, t_m = f"{now.hour:02d}", f"{now.minute:02d}"

        if task:
            try:
                dt = datetime.strptime(task["date"], "%d.%m.%Y")
                tm = datetime.strptime(task["time"], "%H:%M")
                d_day, d_mon, d_yr = f"{dt.day:02d}", f"{dt.month:02d}", str(dt.year)
                t_h, t_m = f"{tm.hour:02d}", f"{tm.minute:02d}"
            except Exception:
                pass

        dd_day = ft.Dropdown(options=[ft.dropdown.Option(d) for d in days], value=d_day, width=80, content_padding=8)
        dd_mon = ft.Dropdown(options=[ft.dropdown.Option(m) for m in months], value=d_mon, width=80, content_padding=8)
        dd_yr = ft.Dropdown(options=[ft.dropdown.Option(y) for y in years], value=d_yr, width=110, content_padding=8)
        dd_hour = ft.Dropdown(options=[ft.dropdown.Option(h) for h in hours], value=t_h, width=80, content_padding=8)
        dd_min = ft.Dropdown(options=[ft.dropdown.Option(m) for m in minutes], value=t_m, width=80, content_padding=8)

        def save_action(e):
            if not name_input.value.strip(): return
            date_str = f"{dd_day.value}.{dd_mon.value}.{dd_yr.value}"
            time_str = f"{dd_hour.value}:{dd_min.value}"

            try:
                datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M")
            except ValueError:
                return

            # Сохраняем значение из поля note_input
            if index is None:
                self.tasks.append({
                    "name": name_input.value.strip(),
                    "date": date_str,
                    "time": time_str,
                    "status": "active",
                    "note": note_input.value.strip()
                })
            else:
                self.tasks[index].update({
                    "name": name_input.value.strip(),
                    "date": date_str,
                    "time": time_str,
                    "note": note_input.value.strip()
                })

            self.save_tasks()
            close_dialog()
            self.refresh_list()

        def delete_action(e):
            if index is not None:
                del self.tasks[index]
                self.save_tasks()
            close_dialog()
            self.refresh_list()

        def toggle_status_action(e):
            if index is not None:
                self.tasks[index]["status"] = "active" if self.tasks[index]["status"] == "performed" else "performed"
                self.save_tasks()
            close_dialog()
            self.refresh_list()

        def close_dialog():
            dialog.open = False
            self.page.update()

        actions = [ft.TextButton("Сохранить", on_click=save_action)]
        if index is not None:
            is_perf = task["status"] == "performed"
            actions.insert(0,
                           ft.TextButton("Удалить", on_click=delete_action, style=ft.ButtonStyle(color=ft.Colors.RED)))
            actions.insert(0, ft.TextButton("В работу" if is_perf else "Выполнено", on_click=toggle_status_action))

        dialog = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Column([
                name_input,
                note_input,  # Размещаем поле заметки под названием задачи
                ft.Text("Дата дедлайна:", size=12, weight=ft.FontWeight.W_500),
                ft.Row([dd_day, dd_mon, dd_yr], spacing=6),
                ft.Text("Время дедлайна:", size=12, weight=ft.FontWeight.W_500),
                ft.Row([dd_hour, ft.Text(":"), dd_min], spacing=6),
            ], tight=True, spacing=10),
            actions=actions
        )

        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()


if __name__ == "__main__":
    ft.run(TaskManagerApp)
