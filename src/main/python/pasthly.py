#!/usr/bin/env python3
import sys
import os
from datetime import datetime
from pathlib import Path
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Nautilus', '3.0')
from gi.repository import Nautilus, GObject, Gtk, Gdk, GLib
import logging
import logging.config
from yaml import safe_load

__NAUTILUS_PYTHON_DEBUG = os.getenv('NAUTILUS_PYTHON_DEBUG', None)
if __NAUTILUS_PYTHON_DEBUG == 'misc':
    log_configs = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
            },
        },
        'handlers': {
            'default': {
                'level':'INFO',
                'class':'logging.StreamHandler',
            },
        },
        'loggers': {
            '': {
                'handlers': ['default'],
                'level': 'INFO',
                'propagate': True
            }
        }
    }
    logging.config.dictConfig(log_configs)
    logger = logging.getLogger(__name__)

    locations = [
        Path('/usr/share/nautilus-python/extensions'),
        Path('/usr/share/ubuntu/nautilus-python/extensions'),
        Path('/usr/share/gnome/nautilus-python/extensions'),
        Path('/usr/local/share/nautilus-python/extensions'),
        Path(os.getenv('HOME')) / '.local/share/nautilus-python/extensions' if os.getenv('HOME') else None,
    ]
    files = [
        (Path('logging.yml'), Path('logging.yaml')),
        (Path('pasthly.yml'), Path('pasthly.yaml')),
        (Path(os.getenv('CFG_LOG')).absolute() if os.getenv('CFG_LOG') else None, None)
    ]
    for i, folder in enumerate(locations):
        if not folder or not folder.exists():
            continue
        for yml, yaml in files:
            selected = yaml if yaml else yml
            if not selected:
                continue
            selected = selected if selected.is_absolute() else folder / selected
            if not selected.exists():
                continue
            with selected.open() as file:
                data = safe_load(file)
            log_configs = log_configs | data
            logging.config.dictConfig(log_configs)
    logger.info('Final log configs: %s', log_configs)


class Pasthly(GObject.GObject, Nautilus.MenuProvider, Nautilus.LocationWidgetProvider):

    def __init__(self, logger=None):
        self.accel_group = Gtk.AccelGroup()
        keyval, modifier = Gtk.accelerator_parse('<Shift><Control>v')
        self.accel_group.connect(keyval, modifier, Gtk.AccelFlags.VISIBLE,
                                         self._shortcuts_handler)
        self.window = None
        self.destination = None
        self.logger = logger or logging.getLogger(__name__)

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
            dialog.format_secondary_text("PasthlY does not know where to paste the hard links")
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
        return None # Do not show whit files selected

    def get_background_items(self, window, folder) -> list[Nautilus.MenuItem]:
        path = self.extract_path(folder)
        if path != self.destination:
            self.destination = path
        menuitem = Nautilus.MenuItem(name='Pasthly::paste_as_hard_link', 
                                         label='Paste as Hard Link', 
                                         tip='<Shift><Control>V',
                                         icon='')
        menuitem.sensitive = False
        menuitem.connect('activate', self._click_handler)
        return [menuitem]

    def _click_handler(self, widget):
        return self.handle_paste()

    def extract_path(self, folder):
        if not folder:
            self.logger.warning('Folder should be non-None')
            return None
        if not folder.is_directory():
            self.logger.warning('%s(%s) should be a directory/folder', folder, folder.get_uri())
            return None
        if not folder.can_write():
            self.logger.warning("PasthlY can't write on the destination folder: %s", folder)
        path = folder.get_location()
        if not path:
            self.logger.warning('Folder location should be non-None')
            if folder.get_uri_scheme() != 'file://':
                self.logger.warning('Folder URI scheme should be of file (file://)')
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