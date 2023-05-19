#!/usr/bin/env python3
import sys
import os
from datetime import datetime
from pathlib import Path
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Nautilus', '3.0')
from gi.repository import Nautilus, GObject, Gtk, Gdk, GLib


class Pasthly(GObject.GObject, Nautilus.MenuProvider, Nautilus.LocationWidgetProvider):

    def __init__(self):
        self.accel_group = Gtk.AccelGroup()
        keyval, modifier = Gtk.accelerator_parse('<Shift><Control>v')
        self.accel_group.connect(keyval, modifier, Gtk.AccelFlags.VISIBLE,
                                         self._shortcuts_handler)
        self.window = None
        self.destination = None

    def _shortcuts_handler(self, *args):
        return self.handle_paste()

    def handle_paste(self):
        files = self.files_from_clipboard()
        if not self.destination:
            dialog = Gtk.MessageDialog(
                transient_for=self.window,
                flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.CANCEL,
                text="Unexpected State",
            )
            dialog.format_secondary_text(
                "PasthlY does not know where to paste the hard links"
            )
            dialog.run()
            dialog.destroy()
            return False
        duplicates = self.paste_as_hard_link(files, self.destination)
        if duplicates:
            dialog = Gtk.MessageDialog(
                transient_for=self.window,
                flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.CANCEL,
                text="PasthlY doesn't overwrite",
            )
            dialog.format_secondary_text(
                '\n'.join(["Those files already exist:"] + [str(d.absolute()) for d in duplicates])
            )
            dialog.run()
            dialog.destroy()
            return False
        return True

    def files_from_clipboard(self):
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        lines = clipboard.wait_for_text()
        if lines is None:
            return []
        return [file for file in [Path(line) for line in lines.split('\n')] if file.exists()]
        

    def get_file_items(self, window, files) -> list[Nautilus.MenuItem]:
        return None # Do not exibt whit files selected

    def get_background_items(self, window, folder) -> list[Nautilus.MenuItem]:
        path = self.extract_path(folder)
        if path != self.destination:
            self.destination = path
        menuitem = Nautilus.MenuItem(name='Pasthly::paste_as_hard_link', 
                                         label='Paste as Hard Link', 
                                         tip='',
                                         icon='')
        menuitem.sensitive = False
        menuitem.connect('activate', self._click_handler)
        return [menuitem]

    def _click_handler(self, widget):
        return self.handle_paste()

    def extract_path(self, folder):
        if not folder:
            print('That is weird, folder should be non-None')
            return None
        if not folder.is_directory():
            print(f'That is weird, {folder}({folder.get_uri()}) should be a directory/folder')
            return None
        if not folder.can_write():
            print('That is akward, it only makes sense to paste as hard link if it can write')
        path = folder.get_location()
        if not path:
            print('That makes things dificult...')
            if folder.get_uri_scheme() != 'file://':
                print('I give up! Not even a file:// ?!') #maiybe is SaMBa (smb://)
                return None
            path = folder.get_uri().removeprefix(folder.get_uri_scheme())
        else:
            path = path.get_path()
        return Path(path)

    def get_widget(self, uri, window):
        if self.window:
            self.window.remove_accel_group(self.accel_group)
        window.add_accel_group(self.accel_group)
        self.window = window
        return None

    def paste_as_hard_link(self, files, target):
        duplicated = []
        destinations = []
        for file in files:
            destination = target / file.name
            if destination.exists():
                duplicated.append(destination)
            else:
                destinations.append((destination, file))
        if duplicated:
            return duplicated
        for link, file in destinations:
            link.hardlink_to(file)
        return []
        


def main():
    return 0


if __name__ == '__main__':
    sys.exit(main())