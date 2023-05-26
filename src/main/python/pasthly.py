#!/usr/bin/env python3
import sys
import os
import logging
import logging.config
from datetime import datetime
from pathlib import Path
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Nautilus', '3.0')
from gi.repository import Nautilus, GObject, Gtk, Gdk, GLib
from yaml import safe_load


SCRIPT_NAME = 'pasthly.py'
logger = None
locations = [
        Path('/usr/share/nautilus-python/extensions'),
        Path('/usr/share/ubuntu/nautilus-python/extensions'),
        Path('/usr/share/gnome/nautilus-python/extensions'),
        Path('/usr/local/share/nautilus-python/extensions'),
        Path(os.getenv('HOME')) / '.local/share/nautilus-python/extensions' if os.getenv('HOME') else None,
    ]

__NAUTILUS_PYTHON_DEBUG = os.getenv('NAUTILUS_PYTHON_DEBUG', None)
if __NAUTILUS_PYTHON_DEBUG == 'misc' or __name__ == '__main__':
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
    logger = logger if logger else logging.getLogger(__name__)

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
    logger.debug('Final log configs: %s', log_configs)


class Pasthly(GObject.GObject, Nautilus.MenuProvider, Nautilus.LocationWidgetProvider):

    def __init__(self, logger=None):
        self.accel_group = Gtk.AccelGroup()
        keyval, modifier = Gtk.accelerator_parse('<Shift><Control>V')
        self.accel_group.connect(keyval, modifier, Gtk.AccelFlags.VISIBLE,
                                         self._handle_shortcut)
        self.window = None
        self.destination = None
        self.logger = logger or logging.getLogger(__name__)

    def get_file_items(self, window, files) -> list[Nautilus.MenuItem]:
        return None # Do not show while files selected

    def get_background_items(self, window, folder) -> list[Nautilus.MenuItem]:
        path = self.extract_path(folder)
        if path and path != self.destination:
            self.destination = path
        if not folder.can_write():
            self.logger.warning("PasthlY can't write on the destination folder: %s", folder)
            return []
        for file in self.files_from_clipboard():
            if file.stat().st_dev != self.destination.stat().st_dev:
                return []
        menuitem = Nautilus.MenuItem(name='Pasthly::paste_as_hard_link', 
                                         label='Paste as Hard Link', 
                                         tip='<Shift><Control>V',
                                         icon='')
        menuitem.connect('activate', self._handle_click)
        return [menuitem]

    def get_widget(self, uri, window):
        if self.window:
            self.window.remove_accel_group(self.accel_group)
        window.add_accel_group(self.accel_group)
        self.window = window
        return None

    ###

    def _handle_shortcut(self, *args):
        return self.handle_paste()

    def _handle_click(self, widget):
        return self.handle_paste()

    def handle_paste(self):
        files = self.files_from_clipboard()
        try:
            self.paste_as_hard_link(files, self.destination)
        except PasthlyError as e:
            self.handle_error(e)
            return False
        return True

    def handle_error(self, error):
        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.CANCEL,
            text=error.title if error.title else 'Error',
        )
        dialog.format_secondary_text(error.message)
        dialog.run()
        dialog.destroy()
        return error.code

    def handle_duplicates(self):
        pass # TODO Issue #7

    def files_from_clipboard(self):
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        lines = clipboard.wait_for_text()
        if lines is None:
            return []
        lines = lines.split('\n')
        files = [file for file in [Path(line) for line in lines] if file.exists()]
        if not files:
            return []
        mismatches = [f for f in files if f.parent != files[0].parent]
        if mismatches:
            self.logger.warn("Files from diferent parent folder: %s", mismatches)
            return []
        return files

    def extract_path(self, folder):
        if not folder:
            self.logger.warning('Folder should be non-None')
            return None
        if not folder.is_directory():
            self.logger.warning('%s(%s) should be a directory/folder', folder, folder.get_uri())
            return None
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

    def paste_as_hard_link(self, files, target):
        if not target:
            raise PasthlyError(code=1, title="Unexpected State", message="PasthlY does not know where to paste the hard links")
        duplicated = []
        destinations = []
        origin_dir = None
        for file in files:
            if file.stat().st_dev != target.stat().st_dev:
                message = 'It is not possible to make hard links from a different device.'
                raise PasthlyError(message, code=4, title='Different filesystems')
            origin_dir = origin_dir if origin_dir else file.parent
            if origin_dir.absolute() != file.parent.absolute():
                message = f"The file '{file}' is not on the same folder of the other files on the clipboard."
                raise PasthlyError(message, code=3, title='Multiple source folders')
            destination = target / file.name
            if destination.exists():
                duplicated.append(destination)
            else:
                destinations.append((destination, file))
        if duplicated:
            text = '\n'.join(["Those files already exist:"] + [str(d.absolute()) for d in duplicated])
            raise PasthlyError(text, code=2, title="PasthlY doesn't overwrite")
        try:
            for link, file in destinations:
                link.hardlink_to(file)
        except OSError as ose:
            message = "Could not finish the creation of the hard links"
            raise PasthlyError(message, code=10, title='Unexpected Error') from ose
        return []

class PasthlyError(Exception):

    def __init__(self, message, code=-1, title=None):
        super(PasthlyError, self).__init__(message)
        self.code = code
        self.title = title
        self.message = message


def install(logger=None):
    logger = logger if logger else logging.getLogger(__name__)
    self = Path(__file__)
    for folder in locations:
        if not folder.exists():
            logger.info("'%s' doesn't exist.", folder)
            continue
        script = folder / SCRIPT_NAME
        if script.exists():
            logger.info("PasthlY (apparently) alreay installed at '%s'", script)
            return 0
        if not os.access(folder, os.W_OK):
            logger.info("'%s' is not writable, skimping it.", folder)
            continue
        try:
            script.write_text(self.read_text())
            logger.info("PasthlY installed at '%s'", script)
            return 0
        except:
            logger.exception("Couldn't copy '%s' to '%s'", self, script)
            continue
    logger.error("No avaliable location for instalation.")
    if not locations[-1]:
        logger.info("TIP: try to create '%s'", locations[-1])
    return 0

def main():
    import argparse

    parser = argparse.ArgumentParser(
        prog=SCRIPT_NAME,
        description='A Python "Paste As Hard Link" Nautilus Extension',
        epilog='See https://github.com/theoamonteiro/pasthly')
    parser.add_argument('--install', action='store_true', required=True)

    args = parser.parse_args(sys.argv[1:])

    return install()


if __name__ == '__main__':
    sys.exit(main())