# MusicApp - Modern Music Player

A feature-rich music player application built with Python using PyQt5 for the GUI and pygame for audio playback. It includes advanced file management capabilities and Last.fm integration.

## Features

### Music Playback
- Play, pause, and stop audio files
- Volume control
- Seek bar for precise playback control
- Support for multiple audio formats (wav, ogg, mp3, mid, midi, flac, aif, aiff, mp2)
- Looping option

### File Management
- Browse and organize your music collection
- Create and manage playlists
- Cut, copy, and paste files
- Rename files and create new folders
- Sort files alphabetically
- Shuffle audio files

### Last.fm Integration
- Connect your Last.fm account
- View connection status
- Login/Logout functionality

### User Interface
- Modern, intuitive design
- Tree view file browser
- Customizable volume control
- Real-time seek bar
- Status indicators
- Context menus for file operations

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/KronosWasTaken/MusicApp.git
   cd MusicApp
   ```
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Launch the application:
```bash
python main.py
```

- Select your music folder using the browse button (📁)
- Double-click any audio file to play
- Use the playback controls at the bottom of the window
- Right-click files for additional options (rename, delete, etc.)

## Configuration

The application will automatically create a configuration file at `~/.musicapp/settings.ini` to save your preferences, including:

- Last played song
- Volume settings
- Folder path
- Playback position

## Supported Audio Formats
- WAV (.wav)
- OGG (.ogg)
- MP3 (.mp3)
- MIDI (.mid, .midi)
- FLAC (.flac)
- AIFF (.aif, .aiff)
- MP2 (.mp2)

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature-branch`)
3. Commit your changes (`git commit -m 'Add new feature'`)
4. Push to the branch (`git push origin feature-branch`)
5. Create a new Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- **PyQt5** for the graphical user interface
- **pygame** for audio playback
- **Last.fm API** for music scrobbling
