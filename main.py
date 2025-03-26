import configparser
from pathlib import Path
import sys
import os
import datetime
import shutil
import random
import pygame
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
                            QPushButton, QLabel, QInputDialog, QMessageBox, QHBoxLayout,
                            QSlider, QAbstractItemView, QMenu, QAction, QLineEdit, QHeaderView,
                            QFileDialog)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt, QTimer, QPoint, QThread, pyqtSignal
from last_fm import LastFMClient
from dotenv import load_dotenv
pygame.mixer.init()

SUPPORTED_AUDIO_EXTENSIONS = {'.wav', '.ogg', '.mp3', '.mid', '.midi', '.flac', '.aif', '.aiff', '.mp2'}

class AuthThread(QThread):
    finished = pyqtSignal(bool)
    
    def __init__(self, client):
        super().__init__()
        self.client = client
        
    def run(self):
        success = self.client.authenticate()
        self.finished.emit(success)

class AudioPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_files()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.timer_trigger)
        self.timer.start(100)
        self.paused = False
        self.last_seek_position = 0
        self.clipboard = []
        self.cut_mode = False
        self.active_playlist_index = -1
        self.slider_grabbed = False
        self.PlayerStarted = False
        self.load_settings()
        self.lastfm_client = LastFMClient()
        self.connected=bool(self.lastfm_client.session_key)
        self.init_lastfm_menu()
        

    def init_ui(self):
        central_widget = QWidget()
        self.layout = QVBoxLayout(central_widget)
        self.setCentralWidget(central_widget)
        self.setWindowTitle("MusicApp")
        self.resize(600, 800)
        self.load_stylesheet()
        self.init_menu_bar()
        self.init_file_browser()
        self.init_audio_controls()
        self.layout.addLayout(self.controls_layout)

    def init_menu_bar(self):
        self.menu_layout = QHBoxLayout()

        # --- Navigation Controls ---
        # Browse button
        self.browse_button = QPushButton("📁", self)
        self.browse_button.setToolTip("Choose music folder")
        self.browse_button.setFixedSize(30, 30)
        self.browse_button.clicked.connect(self.choose_music_directory)
        self.menu_layout.addWidget(self.browse_button)

        # Parent folder button
        self.parent_folder_button = QPushButton("^", self)
        self.parent_folder_button.setToolTip("Go to parent folder")
        self.parent_folder_button.setFixedSize(30, 30)
        self.parent_folder_button.clicked.connect(self.go_to_parent_directory)
        self.menu_layout.addWidget(self.parent_folder_button)

        # --- Path Display ---
        self.folder_path_field = QLineEdit(self)
        self.folder_path_field.setText(self.get_default_music_directory())
        self.folder_path_field.setFixedHeight(30)
        self.folder_path_field.setReadOnly(True)
        self.menu_layout.addWidget(self.folder_path_field)

        # --- Settings Menu ---
        self.settings_menu = QMenu(self)
        # Loop audio toggle
        self.loop_audio_action = QAction("Loop Audio", self)
        self.loop_audio_action.setCheckable(True)
        self.loop_audio_action.setChecked(False)
        self.settings_menu.addAction(self.loop_audio_action)

        self.setWindowIcon(QIcon(self.get_resource_path("icons/app_icon.svg")))

        # Hamburger menu button
        icon_path = self.get_resource_path('icons/hamburger_menu_icon.svg')
        if os.path.exists(icon_path):
            self.hamburger_button = QPushButton(self)
            self.hamburger_button.setIcon(QIcon(icon_path))
            self.hamburger_button.setIconSize(self.hamburger_button.size())
            self.hamburger_button.setFixedSize(30, 30)
            self.hamburger_button.setStyleSheet("QPushButton::menu-indicator {image: none;}")
            self.hamburger_button.setMenu(self.settings_menu)
            self.menu_layout.addWidget(self.hamburger_button)
        else:
            self.log("Warning: Hamburger menu icon not found.")

        # Add completed menu bar to main layout
        self.layout.addLayout(self.menu_layout)

    def init_file_browser(self):
        self.file_browser = QTreeWidget()
        self.file_browser.setColumnCount(2)
        self.file_browser.setHeaderLabels(["Name", "Type"])
        self.file_browser.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.file_browser.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_browser.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.file_browser.customContextMenuRequested.connect(self.show_right_click_menu)
        self.file_browser.itemDoubleClicked.connect(self.file_item_double_clicked)
        header = self.file_browser.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setStretchLastSection(False)
        self.layout.addWidget(self.file_browser)
        QTimer.singleShot(0, self.resize_columns)

    def resize_columns(self):
        total_width = self.file_browser.viewport().width()
        if total_width > 0:
            self.file_browser.setColumnWidth(0, int(total_width * 0.8))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resize_columns()

    def init_audio_controls(self):
        self.init_audio_labels()
        self.init_seek_bar()
        self.init_control_buttons()
        self.init_volume_slider()

    def init_audio_labels(self):
        self.active_audio_name_label = QLabel("No Audio Playing", self)
        self.active_audio_name_label.setAlignment(Qt.AlignCenter)
        self.active_audio_name_label.setStyleSheet("font-size: 16pt; padding: 10px 0;")
        self.layout.addWidget(self.active_audio_name_label)

    def init_seek_bar(self):
        self.slider_layout = QHBoxLayout()

        self.current_playtime_label = QLabel("0:00", self)
        self.audio_length_label = QLabel("0:00", self)
        label_style = "font-size: 20px; padding: 0 10px;"
        self.current_playtime_label.setStyleSheet(label_style)
        self.audio_length_label.setStyleSheet(label_style)

        self.seek_slider = QSlider(Qt.Horizontal, self)
        self.seek_slider.setMinimum(0)
        self.seek_slider.setValue(0)
        self.seek_slider.setDisabled(True)
        self.seek_slider.sliderPressed.connect(self.seek_slider_grabbed)
        self.seek_slider.sliderReleased.connect(self.seek_slider_released)
        self.seek_slider.mousePressEvent = self.seek_slider_clicked

        self.slider_layout.addWidget(self.current_playtime_label)
        self.slider_layout.addWidget(self.seek_slider)
        self.slider_layout.addWidget(self.audio_length_label)
        self.layout.addLayout(self.slider_layout)

    def init_control_buttons(self):
        self.controls_layout = QHBoxLayout()

        self.prev_button = self.create_button("|◁", self.play_previous_audio_file, "Plays the previous audio file")
        self.play_button = self.create_button("▶", self.trigger_play_button)
        self.next_button = self.create_button("▷|", self.play_next_audio_file, "Plays the next audio file")

        self.controls_layout.addWidget(self.prev_button)
        self.controls_layout.addWidget(self.play_button)
        self.controls_layout.addWidget(self.next_button)

        self.layout.addLayout(self.controls_layout)

    def init_volume_slider(self):
        self.volume_slider = QSlider(Qt.Vertical, self)
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(50)
        self.volume_slider.setFixedHeight(100)
        self.volume_slider.valueChanged.connect(self.change_volume)
        self.volume_slider.mousePressEvent = self.volume_slider_clicked
        self.slider_layout.addWidget(self.volume_slider)

    def get_config_path(self):
        config_dir = Path.home() / ".musicapp"
        config_dir.mkdir(exist_ok=True)
        return config_dir / "settings.ini"

    def load_settings(self):
        config = configparser.ConfigParser()
        config_path = self.get_config_path()

        if config_path.exists():
            try:
                config.read(config_path)
                # Load volume
                self.volume_slider.setValue(int(config.get('DEFAULT', 'volume', fallback=50)))
                # Load folder path
                saved_path = config.get('DEFAULT', 'folder_path', fallback="")
                if saved_path:
                    self.folder_path_field.setText(saved_path)
                    self.load_files()
                # Load playback state
                current_song = config.get('DEFAULT', 'current_song', fallback="")
                last_position = float(config.get('DEFAULT', 'last_position', fallback=0))
                was_playing = config.getboolean('DEFAULT', 'was_playing', fallback=False)

                if current_song:
                    QTimer.singleShot(500, lambda: self.restore_playback(current_song, last_position, was_playing))

            except Exception as e:
                self.log(f"Error loading settings: {e}")

    def save_settings(self):
        config = configparser.ConfigParser()
        config['DEFAULT'] = {
            'volume': str(self.volume_slider.value()),
            'folder_path': self.folder_path_field.text(),
            'current_song': self.active_audio_name_label.text() if self.active_audio_name_label.text() != "No Audio Playing" else "",
            'last_position': str(self.last_seek_position),
            'was_playing': str(not self.paused)
        }

        try:
            with open(self.get_config_path(), 'w') as configfile:
                config.write(configfile)
        except Exception as e:
            self.log(f"Error saving settings: {e}")

    def restore_playback(self, song_name, position, was_playing):
        for i in range(self.file_browser.topLevelItemCount()):
            item = self.file_browser.topLevelItem(i)
            if item.text(0) == song_name:
                self.play_audio(self.get_file_browser_item_path(item))

                QTimer.singleShot(100, lambda:pygame.mixer.music.set_pos(position) if pygame.mixer.music.get_busy() else None)

                self.last_seek_position = position
                self.seek_slider.setValue(int(position))
                self.current_playtime_label.setText(self.format_time(position))

                if not was_playing:
                    self.trigger_play_button()
                return
        self.log(f"Previous song '{song_name}' not found in current folder")

    def closeEvent(self, event):
        self.save_settings()
        super().closeEvent(event)

    def create_button(self, text, callback, tooltip=None):
        button = QPushButton(text, self)
        button.clicked.connect(callback)
        button.setFixedHeight(40)
        if tooltip:
            button.setToolTip(tooltip)
        return button

    def load_stylesheet(self):
        try:
            css_path = self.get_resource_path('style.css')
            with open(css_path, 'r') as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            print("CSS file not found!")

    def choose_music_directory(self):
        dialog = QFileDialog()
        folder_path = dialog.getExistingDirectory(
            self,
            "Select Music Folder",
            self.get_default_music_directory(),
            QFileDialog.ShowDirsOnly
        )
        if folder_path:
            self.folder_path_field.setText(folder_path)
            self.load_files()

    def show_right_click_menu(self, pos: QPoint):
        menu = QMenu(self)
        selected_items = self.file_browser.selectedItems()
        if selected_items:
            play_action = QAction("Play")
            play_action.triggered.connect(self.play_first_selected_file)
            menu.addAction(play_action)
            rename_action = QAction("Rename", self)
            rename_action.triggered.connect(self.rename_file)
            rename_action.setEnabled(len(selected_items) == 1)
            menu.addAction(rename_action)
            for action_name, method in {"Cut": self.cut_files, "Copy": self.copy_files, "Paste": self.paste_files,
                                        "Delete": self.delete_files}.items():
                action = QAction(action_name)
                action.triggered.connect(method)
                menu.addAction(action)
        for action_name, method in {"Create New Folder": self.create_new_folder, "Refresh Directory": self.load_files,
                                    "Sort A - Z": self.sort_files,
                                    "Shuffle Audio Files": self.shuffle_audio_files}.items():
            action = QAction(action_name)
            action.triggered.connect(method)
            menu.addAction(action)
        menu.exec_(self.file_browser.viewport().mapToGlobal(pos))

    def load_files(self):
        self.file_browser.clear()
        path = self.folder_path_field.text()
        try:
            with os.scandir(path) as entries:
                folders, audio_files = [], []
                for entry in entries:
                    (folders if entry.is_dir() else audio_files).append(entry.name)
                for folder in sorted(folders):
                    self.file_browser.addTopLevelItem(QTreeWidgetItem([folder]))
                for audio_file in sorted(audio_files):
                    self.file_browser.addTopLevelItem(QTreeWidgetItem([audio_file]))
        except Exception as e:
            self.log(f"Error loading files: {e}", error=True)

    def file_item_double_clicked(self, item, column):
        current_path = self.folder_path_field.text()
        new_path = os.path.join(current_path, item.text(0))
        if os.path.isdir(new_path):
            self.folder_path_field.setText(new_path)
            self.load_files()
        elif item.text(0).lower().endswith(tuple(SUPPORTED_AUDIO_EXTENSIONS)):
            self.play_audio(self.get_file_browser_item_path(item))

    def go_to_parent_directory(self):
        parent_path = os.path.dirname(self.folder_path_field.text())
        if parent_path:
            self.folder_path_field.setText(parent_path)
            self.load_files()

    def play_audio(self, audio_path):
        self.PlayerStarted = True
        self.log(f"Attempting to play: {audio_path}")
        if not os.path.exists(audio_path):
            self.log("Invalid path.")
            return
        pygame.mixer.music.load(audio_path)
        pygame.mixer.music.play(start=0)
        self.active_audio_name_label.setText(os.path.basename(audio_path))
        self.current_playtime_label.setText("0:00")
        self.paused = False
        self.last_seek_position = 0
        self.seek_slider.setDisabled(False)
        sound = pygame.mixer.Sound(audio_path)
        self.audio_length_label.setText(self.format_time(sound.get_length()))
        self.play_button.setText("||")

    def play_first_audio_in_folder(self):
        for i in range(self.file_browser.topLevelItemCount()):
            item = self.file_browser.topLevelItem(i)
            if item.text(1) != "Folder":
                self.file_browser.clearSelection()
                item.setSelected(True)
                self.play_audio(self.get_file_browser_item_path(item))
                return

    def play_first_selected_file(self):
        selected_items = self.file_browser.selectedItems()
        if selected_items:
            self.play_audio(self.get_file_browser_item_path(selected_items[0]))

    def play_first_audio(self):
        selected_items = self.file_browser.selectedItems()
        if selected_items:
            self.play_audio(self.get_file_browser_item_path(selected_items[0]))
        else:
            self.play_first_audio_in_folder()

    def trigger_play_button(self):
        if self.active_audio_name_label.text() == "No Audio Playing":
            self.play_first_audio()
        elif self.paused:
            pygame.mixer.music.unpause()
            self.paused = False
            self.play_button.setText("||")
        else:
            pygame.mixer.music.pause()
            self.play_button.setText("▶")
            self.paused = True

    def play_next_audio_file(self):
        active_index = self.get_active_audio_index()
        self.log(f"Active index: {active_index}")
        if active_index != -1:
            next_audio_item = self.file_browser.topLevelItem(active_index + 1)
            if next_audio_item:
                self.file_browser.clearSelection()
                next_audio_item.setSelected(True)
                self.play_audio(self.get_file_browser_item_path(next_audio_item))
                return
            self.log("Reached the end of the list, playing first audio.")
        self.play_first_audio_in_folder()
        self.file_browser.clearFocus()

    def play_previous_audio_file(self):
        active_index = self.get_active_audio_index()
        if active_index != -1:
            prev_audio_item = self.file_browser.topLevelItem(active_index - 1)
            if prev_audio_item:
                if prev_audio_item.text(1) == "Folder":
                    last_audio_item = self.file_browser.topLevelItem(self.file_browser.topLevelItemCount() - 1)
                    self.file_browser.clearSelection()
                    last_audio_item.setSelected(True)
                    self.play_audio(self.get_file_browser_item_path(last_audio_item))
                    return
                self.file_browser.clearSelection()
                prev_audio_item.setSelected(True)
                self.play_audio(self.get_file_browser_item_path(prev_audio_item))
                return
            self.play_first_audio_in_folder()

    def rename_file(self):
        current_path = self.folder_path_field.text()
        selected_items = self.file_browser.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Rename", "No file or folder selected.")
            return
        item = selected_items[0]
        old_name = item.text(0)
        file_extension = item.text(1)
        new_name, ok = QInputDialog.getText(self, "Rename", "Enter new name:", text=old_name)
        if not ok or not new_name.strip():
            return
        new_path = os.path.join(current_path, new_name)
        if os.path.exists(new_path + file_extension):
            QMessageBox.warning(self, "Rename", "A file or folder with this name already exists.")
            return
        try:
            os.rename(os.path.join(current_path, old_name) + file_extension, new_path + file_extension)
            self.load_files()
        except Exception as e:
            self.log(f"Error renaming file: {e}", error=True)

    def cut_files(self):
        self.clipboard = [self.get_file_browser_item_path(item) for item in self.file_browser.selectedItems()]
        self.cut_mode = True
        print("Cut items stored in clipboard:", self.clipboard)

    def copy_files(self):
        self.clipboard = [self.get_file_browser_item_path(item) for item in self.file_browser.selectedItems()]
        self.cut_mode = False
        print("Copied items stored in clipboard:", self.clipboard)

    def paste_files(self):
        if not self.clipboard:
            QMessageBox.warning(self, "Paste", "Clipboard is empty.")
            return
        current_path = self.folder_path_field.text()
        selected_items = self.file_browser.selectedItems()
        destination_path = next(
            (os.path.join(current_path, item.text(0)) for item in selected_items if item.text(1) == "Folder"),
            current_path)
        for item_path in self.clipboard:
            item_name = os.path.basename(item_path)
            new_path = os.path.join(destination_path, item_name)
            if os.path.exists(new_path):
                base, ext = os.path.splitext(item_name)
                counter = 1
                while os.path.exists(new_path):
                    new_path = os.path.join(destination_path, f"{base}_copy{counter}{ext}")
                    counter += 1
            try:
                if os.path.isdir(item_path):
                    shutil.move(item_path, new_path) if self.cut_mode else shutil.copytree(item_path, new_path)
                else:
                    shutil.move(item_path, new_path) if self.cut_mode else shutil.copy2(item_path, new_path)
            except Exception as e:
                self.log(f"Error pasting files: {e}", error=True)
        if self.cut_mode:
            self.clipboard = []
            self.cut_mode = False
        self.load_files()

    def delete_files(self):
        selected_items = self.file_browser.selectedItems()
        if selected_items:
            for item in selected_items:
                item_name = item.text(0)
                item_path = self.get_file_browser_item_path(item)
                if QMessageBox.question(self, "Delete", f"Are you sure you want to delete '{item_name}'?",
                                        QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                    try:
                        if os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                        else:
                            os.remove(item_path)
                        self.log(f"Deleted: {item_path}")
                    except Exception as e:
                        self.log(f"Error deleting {item_path}: {e}")
        self.load_files()

    def create_new_folder(self):
        current_path = self.folder_path_field.text()
        folder_name, ok = QInputDialog.getText(self, "New Folder", "Enter folder name:")
        if ok and folder_name:
            os.mkdir(os.path.join(current_path, folder_name))
            self.load_files()

    def sort_files(self):
        self.log("Sorted files.")
        self.load_files()

    def shuffle_audio_files(self):
        audio_items = [self.file_browser.takeTopLevelItem(i) for i in
                       range(self.file_browser.topLevelItemCount() - 1, -1, -1) if
                       self.file_browser.topLevelItem(i).text(1) != "Folder"]
        random.shuffle(audio_items)
        for item in audio_items:
            self.file_browser.addTopLevelItem(item)
        for i in range(self.file_browser.topLevelItemCount()):
            item = self.file_browser.topLevelItem(i)
            if item.text(0) == self.active_audio_name_label.text():
                self.file_browser.clearSelection()
                item.setSelected(True)
        self.file_browser.clearFocus()

    def timer_trigger(self):
        if pygame.mixer.music.get_busy():
            self.update_seek_slider_position()
        else:
            if self.PlayerStarted == True and self.paused == False:
                self.play_next_audio_file()

    def update_seek_slider_position(self):
        if self.slider_grabbed:
            return
        current_position = self.last_seek_position + (pygame.mixer.music.get_pos() / 1000) if hasattr(self,
                                                                                                      'last_seek_position') else pygame.mixer.music.get_pos() / 1000
        self.seek_slider.setValue(int(current_position))
        self.seek_slider.setMaximum(int(self.time_to_seconds(self.audio_length_label.text())))
        self.current_playtime_label.setText(self.format_time(current_position))

    def seek_slider_grabbed(self):
        self.slider_grabbed = True
        self.log("User grabbed the seek slider.")

    def seek_slider_released(self):
        self.slider_grabbed = False
        self.log("User released seek slider.")
        seek_time = self.seek_slider.value()
        self.log(f"User seeked to: {seek_time}")
        pygame.mixer.music.stop()
        pygame.mixer.music.play()
        pygame.mixer.music.set_pos(seek_time)
        self.last_seek_position = seek_time
        self.update_seek_slider_position()

    def seek_slider_clicked(self, event):
        if event.button() == Qt.LeftButton:
            value = self.seek_slider.minimum() + (
                        self.seek_slider.maximum() - self.seek_slider.minimum()) * event.x() / self.seek_slider.width()
            self.seek_slider.setValue(int(value))
            self.seek_slider_changed(int(value))

    def seek_slider_changed(self, value):
        total_duration = self.time_to_seconds(self.audio_length_label.text())
        new_position = (value / self.seek_slider.maximum()) * total_duration
        pygame.mixer.music.stop()
        pygame.mixer.music.play()
        pygame.mixer.music.set_pos(new_position)
        self.last_seek_position = new_position
        self.update_seek_slider_position()

    def change_volume(self, value):
        pygame.mixer.music.set_volume(value / 100)
        self.log(f"Volume set to: {value}%")

    def volume_slider_clicked(self, event):
        if event.button() == Qt.LeftButton:
            self.volume_slider.valueChanged.disconnect(self.change_volume)  # Temporarily disconnect
            value = self.volume_slider.minimum() + (self.volume_slider.maximum() - self.volume_slider.minimum()) * (
                        self.volume_slider.height() - event.y()) / self.volume_slider.height()
            self.volume_slider.setValue(int(value))
            self.change_volume(int(value))
            self.volume_slider.valueChanged.connect(self.change_volume)  # Reconnect

    def log(self, message, error=False):
        current_time = datetime.datetime.now().strftime('%H:%M:%S')
        error_tag = "ERROR" if error else "INFO"
        print(f"[{current_time}]{error_tag}: {message}")

    def get_resource_path(self, relative_path):
        return os.path.join(sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.abspath("."), relative_path)

    def get_file_browser_item_path(self, item):
        current_path = self.folder_path_field.text()
        file_name = item.text(0)
        return os.path.join(current_path, file_name) + (item.text(1) if item.text(1) != "Folder" else "")

    def get_active_audio_index(self):
        for i in range(self.file_browser.topLevelItemCount()):
            item = self.file_browser.topLevelItem(i)
            if item.text(0) == self.active_audio_name_label.text():
                self.log(f"Active audio index: {i}")
                return i
        self.log("Index for active audio not found.")
        return -1

    def time_to_seconds(self, time):
        minutes, seconds = map(int, time.split(":"))
        return minutes * 60 + seconds

    def format_time(self, seconds):
        return f"{int(seconds // 60)}:{int(seconds % 60):02d}"

    def get_default_music_directory(self):
        return os.path.expanduser("~/Music")

    def init_lastfm_menu(self):
        self.lastfm_menu = self.menuBar().addMenu('Last.fm')
        
        # Connect action
        
        self.auth_action = QAction("Login to Last.fm", self)
        self.auth_action.triggered.connect( self.handle_lastfm_auth )
        self.lastfm_menu.addAction(self.auth_action)
        
     
        
        # Status indicator
        self.lastfm_status_action = QAction('Not connected', self)
        self.lastfm_status_action.setEnabled(False)
        self.lastfm_menu.addAction(self.lastfm_status_action)

    def update_auth_display(self):
        
        # Update action text
        self.auth_action.setText("Logout from Last.fm" if self.connected else "Login to Last.fm")
        
        # Update status message
        status_text = "Connected" if self.connected else "Not connected"
        self.lastfm_status_action.setText(status_text)

    def handle_lastfm_auth(self):
        if self.connected:
            self.lastfm_client.logout()
            self.connected=False
            QMessageBox.information(self, "Logged Out", "Last.fm session cleared")
            self.update_auth_display()
        else:
            success = self.lastfm_client.authenticate()
            if success:
                self.connected=True
                QMessageBox.information(self, "Success", "Last.fm login successful!")
            self.update_auth_display()
           
            


   

    def handle_auth_result(self, success):
        self.lastfm_button.setEnabled(True)
        self.update_lastfm_status(success)
        if success:
            QMessageBox.information(self, 'Success', 'Authentication successful!')
        else:
            QMessageBox.critical(self, 'Error', 'Authentication failed')

    def update_lastfm_status(self, connected):
        status = 'Connected' if connected else 'Disconnected'
        self.lastfm_status_action.setText(f'Scrobbling Status: {status}')


# ------------------------------ Application Start ------------------------------#

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AudioPlayer()
    window.show()
    sys.exit(app.exec_())
