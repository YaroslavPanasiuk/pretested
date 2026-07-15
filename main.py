#!/usr/bin/env python3
import sys
import os
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk

from model import TestModel
from ui import TestWindow

class TestApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.pretested")
        self.model = TestModel()

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self.load_css()

    def load_css(self):
        css_provider = Gtk.CssProvider()
        css_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "style.css")
        
        if not os.path.exists(css_path):
            css_path = "style.css"

        try:
            css_provider.load_from_path(css_path)
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_USER
            )
        except Exception as e:
            print(f"Warning: Failed to load CSS: {e}")

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = TestWindow(app=self, model=self.model)
        win.present()

if __name__ == "__main__":
    app = TestApp()
    app.run(sys.argv)