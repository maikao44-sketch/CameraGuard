from typing import Callable, Optional

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError as exc:
    raise ImportError("系统托盘功能需要安装依赖: pip install pystray pillow") from exc


def _create_default_icon(size: int = 64) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    dc = ImageDraw.Draw(img)
    dc.ellipse([4, 4, size - 4, size - 4], fill=(37, 99, 235, 255), outline=(147, 197, 253, 255), width=2)
    dc.polygon([(size//2, 12), (size-18, 22), (size-22, 48), (size//2, 56), (18, 48), (14, 22)], fill=(15, 23, 42, 255), outline=(219, 234, 254, 255))
    dc.ellipse([size//2-5, size//2-5, size//2+5, size//2+5], fill=(96, 165, 250, 255))
    return img


class TrayManager:
    def __init__(self, on_show_window: Callable[[], None], on_exit: Callable[[], None], title: str = "CameraGuard", icon: Optional[Image.Image] = None):
        self._on_show = on_show_window
        self._on_exit = on_exit
        self._icon_image = icon or _create_default_icon()
        self._title = title
        self._icon: Optional[pystray.Icon] = None
        self._window_visible = False

    def _build_menu(self):
        def show(item):
            self._window_visible = True
            self._update_menu()
            self._on_show()

        def exit_app(item):
            self._on_exit()
            if self._icon:
                self._icon.stop()

        return pystray.Menu(
            pystray.MenuItem("打开预警看板", show, default=True),
            pystray.MenuItem("退出", exit_app),
        )

    def _update_menu(self):
        if self._icon:
            self._icon.menu = self._build_menu()

    def start(self) -> None:
        self._icon = pystray.Icon("cameraguard", self._icon_image, self._title, menu=self._build_menu())
        self._icon.run()

    def stop(self) -> None:
        if self._icon:
            self._icon.stop()

    def set_window_visible(self, visible: bool) -> None:
        self._window_visible = visible
        self._update_menu()
