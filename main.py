import sys
import os
import warnings

# Suppress cflib legacy firmware deprecation warnings — drone runs old firmware,
# TYPE_HOVER_LEGACY still works correctly, warning just floods the console.
warnings.filterwarnings("ignore", category=DeprecationWarning,
                        message=".*TYPE_HOVER_LEGACY.*")

# Ensure drone_gui/ is on the path so all imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("NanoHawk Control Station")
    app.setOrganizationName("EdgeAI Drone Systems")

    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # DEMO_MODE=True  → fully animated dashboard, no hardware needed (for UI testing)
    # DEMO_MODE=False → real services (Plan B), panels show "Connect Drone First"
    DEMO_MODE = False

    window = MainWindow(demo_mode=DEMO_MODE)

    if not DEMO_MODE:
        from controllers.main_controller import MainController
        controller = MainController()
        window.connect_services(controller)
        controller.start_all()
        app.aboutToQuit.connect(controller.stop_all)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
