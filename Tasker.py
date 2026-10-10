
import os
import sys
import csv
import asyncio
from datetime import datetime
import flet as ft

#CSV_FILE = "tasks.csv"
# ... (остальные ваши импорты) ...

# ОПРЕДЕЛЯЕМ БЕЗОПАСНЫЙ ПУТЬ ДЛЯ CSV (Подходит для ПК и Android)
if hasattr(sys, '_MEIPASS') or os.environ.get('ANDROID_ARGUMENT'):
    # Если запущено на телефоне (Android), сохраняем в системную папку документов приложения.
    # Эта папка изолирована, защищена Android и переносится целиком при обновлениях приложения.
    import platform
    if hasattr(sys, 'getandroidsdk') or 'ANDROID_ARGUMENT' in os.environ:
        # Для Android используем стандартный путь песочницы приложения
        base_path = os.path.expanduser('~')
    else:
        base_path = os.getcwd()
else:
    # Если запускаем на компьютере в PyCharm, сохраняем в текущую папку проекта
    base_path = os.getcwd()

CSV_FILE = os.path.join(base_path, "tasks.csv")
print(f"База данных задач сохраняется по пути: {CSV_FILE}")

# flet run Tasker.py -w --host 0.0.0.0 --port 4444
# https://github.com/972yk/Tasker/blob/main/build.yml
# "C:\Program Files\JetBrains\PyCharm Community Edition 2022.3\jbr\bin\keytool" -genkey -v -keystore tasker-release-key.jks -keyalg RSA -keysize 2048 -validity 10000 -alias tasker-key -storepass PASS11 -keypass PASS11 -dname "CN=Tasker, O=Home, C=US"
# certutil -encode tasker-release-key.jks tmp.b64
# "C:\Program Files\JetBrains\PyCharm Community Edition 2022.3\jbr\bin\keytool" -genkey -v -keystore tasker-release-key.jks -keyalg RSA -keysize 2048 -validity 10000 -alias upload -storepass PASS11 -keypass PASS11 -dname "CN=Tasker, O=Home, C=US"
class TaskManagerApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Менеджер Задач"
        self.page.theme_mode = ft.ThemeMode.SYSTEM
        self.page.window_width = 240
        self.page.window_height = 320
        self.need_refresh = False
        self.app_version = " "
        self.build_num = " "

        if page.platform == ft.PagePlatform.WINDOWS:
            self.page.window.icon = "/icon.ico"
        else:
            self.page.window.icon = "/icon.png"

        # Базовый отступ
        #self.page.padding = 10
        #self.page.padding = ft.Padding(10, 0, 10, 25)

        self.tasks = []
        self.load_tasks()

        # Список задач
        self.task_list_view = ft.ListView(expand=True, spacing=4)


        self.sort_dropdown = ft.Dropdown(
            label="Сортировка",
            value="По времени",
            #value="По порядку",
            options=[
                ft.dropdown.Option("По времени"),
                ft.dropdown.Option("По алфавиту"),
                ft.dropdown.Option("По порядку")
            ],
            width=170,
            content_padding=5
        )
        #self.sort_dropdown.on_change = self.on_sort_changed
        self.sort_dropdown.on_text_change = self.on_sort_changed

        # Компактная кнопка для верхнего угла
        self.add_button = ft.FloatingActionButton(
            content=ft.Row([ft.Icon(ft.Icons.ADD, size=16), ft.Text("Добавить", size=11)],
                           alignment=ft.MainAxisAlignment.CENTER),
            on_click=self.open_add_dialog,
            width=120,
            #height=34
        )

        self.version_button = ft.TextButton(
            content=ft.Text(
                "Версия",
                color=ft.Colors.GREY_600
            ),
            on_click=self.show_about_dialog
        )
        #top_menu_row = ft.Row([self.sort_dropdown, self.add_button], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        top_menu_row = ft.Row([self.sort_dropdown, self.add_button, self.version_button])

        asyncio.create_task(self.update_version_ui())

        # Безопасная зона для статус-бара телефона
        safe_top_panel = ft.SafeArea(
            content=ft.Container(
                content=top_menu_row,
                #margin=ft.Margin(0, 8, 0, 8)
            )
        )

        self.page.add(
            safe_top_panel,
            self.task_list_view,
        )

        self.refresh_list()
        asyncio.create_task(self.background_timer())

    async def update_version_ui(self):
        real_version_text = await self.get_app_version_string()
        self.version_button.text = real_version_text
        self.page.update()

    def show_about_dialog(self, e):
        about_dialog = ft.AlertDialog(
            title=ft.Text("О приложении"),
            content=ft.Text(
                f"Менеджер Задач Tasker\n\n"
                f"{self.version_button.text}\n" # Берем уже готовый текст из кнопки
                f"Платформа: {self.page.platform.value}\n\n"
                f"Все задачи безопасно сохраняются локально."
            ),
            actions=[
                ft.TextButton("Закрыть", on_click=lambda _: self.close_about_dialog(about_dialog))
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.overlay.append(about_dialog)
        about_dialog.open = True
        self.page.update()

    def close_about_dialog(self, dialog):
        dialog.open = False
        self.page.update()

    async def get_app_version_string(self) -> str:
        # Проверяем, запущено ли приложение в режиме сборки (на Android или в скомпилированном .exe)
        # На Android всегда присутствует системный аргумент или MEIPASS
        is_compiled = hasattr(sys, '_MEIPASS') or os.environ.get('ANDROID_ARGUMENT') or hasattr(sys, 'getandroidsdk')

        if is_compiled:
            try:
                # Пытаемся прочитать реальные данные из package_info скомпилированного приложения
                package_info = await self.page.run_task("flet_package_info")
                if package_info:
                    version = package_info.get("version", "1.0.0")
                    build = package_info.get("build_number", "1")
                    return f"Версия: {version} (b{build})"
            except Exception:
                pass  # Если по какой-то причине метод Flet не ответил, спустимся к запасному варианту

        # Если запущено из PyCharm (режим разработки), читаем flet.yaml напрямую
        try:
            # Находим flet.yaml в текущей папке проекта
            yaml_path = os.path.join(os.getcwd(), "flet.yaml")
            if os.path.exists(yaml_path):
                with open(yaml_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                version = "1.0.0"
                build = "1"

                # Парсим строки без использования тяжелых сторонних библиотек (типа PyYAML)
                for line in lines:
                    line = line.strip()
                    if line.startswith("version:"):
                        # Очищаем от кавычек и пробелов
                        version = line.split(":", 1)[1].replace('"', '').replace("'", "").strip()
                    elif line.startswith("build_version:"):
                        build = line.split(":", 1)[1].strip()

                return f"Версия: {version} (b{build})"
        except Exception:
            pass

        # Полный бэкап, если flet.yaml не найден или поврежден
        return "Версия: 1.0.0 (local)"


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
        skip = 0
        while True:
            await asyncio.sleep(0.1)
            skip = skip + 1
            if skip > 100 or self.need_refresh:
                skip = 0
                self.need_refresh = False
                self.refresh_list()

    def on_sort_changed(self, e):
        #self.refresh_list()
        self.need_refresh = True

    def get_sorted_tasks(self):
        indexed_tasks = list(enumerate(self.tasks))
        mode = self.sort_dropdown.value

        if mode == "По времени":
            def parse_dt(item):
                try:
                    return datetime.strptime(f"{item[1]['date']} {item[1]['time']}", "%d.%m.%Y %H:%M")
                except ValueError:
                    return datetime.max

            indexed_tasks.sort(key=parse_dt)
        elif mode == "По алфавиту":
            indexed_tasks.sort(key=lambda item: item[1]["name"].lower())

        return indexed_tasks

    def refresh_list(self):
        try:
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
        except Exception:
            pass

    def open_add_dialog(self, e):
        self.show_task_dialog("Создать задачу", None)

    def open_edit_window(self, index):
        self.show_task_dialog("Редактировать задачу", index)

    def show_task_dialog(self, title, index=None):
        # Импортируем timedelta локально для защиты от сдвига часовых поясов
        from datetime import timedelta

        task = self.tasks[index] if index is not None else None

        name_input = ft.TextField(label="Название задачи", value=task["name"] if task else "", dense=True)
        note_input = ft.TextField(
            label="Заметка / Описание",
            value=task["note"] if task and "note" in task else "",
            multiline=True,
            min_lines=2,
            max_lines=4,
            hint_text="Введите сюда детали задачи...",
            dense=True
        )

        now = datetime.now()
        dialog_state = {
            "date_str": now.strftime("%d.%m.%Y"),
            "time_str": now.strftime("%H:%M")
        }

        if task:
            dialog_state["date_str"] = task["date"]
            dialog_state["time_str"] = task["time"]

        btn_date = ft.OutlinedButton(
            content=ft.Text(dialog_state["date_str"]),
            icon=ft.Icons.CALENDAR_MONTH,
            on_click=lambda e: open_date_picker(e),
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=4))
        )

        btn_time = ft.OutlinedButton(
            content=ft.Text(dialog_state["time_str"]),
            icon=ft.Icons.ACCESS_TIME,
            on_click=lambda e: open_time_picker(e),
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=4))
        )

        # Железобетонная защита от бага часовых поясов Flet
        def on_date_picked(e):
            if e.control.value:
                # Добавляем 12 часов к UTC-времени, чтобы дата гарантированно осталась внутри выбранного дня
                local_dt = e.control.value + timedelta(hours=12)

                # Записываем чистую строковую дату
                new_str = local_dt.strftime("%d.%m.%Y")
                dialog_state["date_str"] = new_str
                btn_date.content.value = new_str
                btn_date.update()

        def on_time_picked(e):
            if e.control.value is not None:
                if isinstance(e.control.value, str):
                    dialog_state["time_str"] = e.control.value
                else:
                    dialog_state["time_str"] = e.control.value.strftime("%H:%M")

                btn_time.content.value = dialog_state["time_str"]
                btn_time.update()

        start_dt = datetime.strptime(dialog_state["date_str"], "%d.%m.%Y")
        start_tm = datetime.strptime(dialog_state["time_str"], "%H:%M").time()

        date_picker = ft.DatePicker(
            current_date=start_dt,
            first_date=datetime(now.year - 1, 1, 1),
            last_date=datetime(now.year + 5, 12, 31),
            on_change=on_date_picked
        )

        time_picker = ft.TimePicker(
            value=start_tm,
            on_change=on_time_picked
        )

        def open_date_picker(e):
            current_btn_dt = datetime.strptime(dialog_state["date_str"], "%d.%m.%Y")
            date_picker.current_date = current_btn_dt
            date_picker.open = True
            date_picker.update()

        def open_time_picker(e):
            time_picker.open = True
            time_picker.update()

        self.page.overlay.extend([date_picker, time_picker])
        self.page.update()

        def save_action(e):
            if not name_input.value.strip(): return

            if index is None:
                self.tasks.append({
                    "name": name_input.value.strip(),
                    "date": dialog_state["date_str"],
                    "time": dialog_state["time_str"],
                    "status": "active",
                    "note": note_input.value.strip()
                })
            else:
                self.tasks[index].update({
                    "name": name_input.value.strip(),
                    "date": dialog_state["date_str"],
                    "time": dialog_state["time_str"],
                    "note": note_input.value.strip()
                })

            self.save_tasks()
            close_dialog()
            self.need_refresh = True

        def delete_action(e):
            if index is not None:
                del self.tasks[index]
                self.save_tasks()
            close_dialog()
            self.need_refresh = True

        def toggle_status_action(e):
            if index is not None:
                self.tasks[index]["status"] = "active" if self.tasks[index]["status"] == "performed" else "performed"
                self.save_tasks()
            close_dialog()
            self.need_refresh = True

        def close_dialog():
            dialog.open = False
            self.page.update()

        actions = [ft.TextButton("Сохранить", on_click=save_action)]
        if index is not None:
            is_perf = task["status"] == "performed"
            actions.insert(0,
                           ft.TextButton("Удалить", on_click=delete_action, style=ft.ButtonStyle(color=ft.Colors.RED)))
            actions.insert(0, ft.TextButton("В работу" if is_perf else "Выполнено", on_click=toggle_status_action))

        dialog_content = ft.Container(
            content=ft.Column([
                name_input,
                note_input,
                ft.Text("Дата дедлайна:", size=12, weight=ft.FontWeight.W_500),
                btn_date,
                ft.Text("Время дедлайна:", size=12, weight=ft.FontWeight.W_500),
                btn_time,
            ], tight=True, spacing=10,
                scroll=ft.ScrollMode.ALWAYS),
            width=330
        )

        dialog = ft.AlertDialog(
            content=dialog_content,
            actions=actions
        )

        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()


if __name__ == "__main__":
    ft.run(TaskManagerApp)
