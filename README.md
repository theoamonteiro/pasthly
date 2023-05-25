# `PasthlY` - A Python "Paste As Hard Link" Nautilus Extension

This project creates an Nautilus Extension to make avalible the possibility to instead of pasting a copy of files (`<Control>V`) in Nautilus (Gnome Files), create hard links to files (`<Shift><Control>V`) on the clipboard.

# Dependencies

- Python 3: `3.11.3`
- PyGObject: `3.24.38`
- gobject-introspection: `3.44.1`
- python3-nautilus: `1.2.3`
- PyYAML: `6.0`

# Known Issues

- It (_only_) works with Nautilus `42` and python3-nautilus `1.2.3`
  - GTK 3 (`gi.required_version('Gtk', '3.0')`) and Nautilus 3 (`gi.required_version('Nautilus', '3.0')`)
- It won't work on Nautilus `43.beta` or later.

---

# Install

```shell
TMP_FILE=$(mktemp); curl 'https://raw.githubusercontent.com/theoamonteiro/pasthly/master/src/main/python/pasthly.py' 2> /dev/null > $TMP_FILE ; python $TMP_FILE --install ; rm -f $TMP_FILE
```

---

# Setup on a Conda Environment

```shell
conda env create --name $NEW_CONDA_ENV_NAME --file environment.yml
pip install -r dependencies.txt
```

## python3-nautilus

Since there is not a conda package, nor a pip package, it is necessary a little hack to get things runing:

1. Install `python3-nautilus` package
2. Create the links for files and folders


```shell
# CONDA_ENV_PATH=/var/opt/anaconda/$USER/envs/nautilus

sudo apt install -y python3-nautilus
ln -s /usr/lib/x86_64-linux-gnu/nautilus $CONDA_ENV_PATH/lib/
ln -s /usr/lib/x86_64-linux-gnu/pkgconfig/nautilus-python.pc $CONDA_ENV_PATH/lib/pkgconfig/
ln -s /usr/lib/x86_64-linux-gnu/girepository-1.0/Nautilus-3.0.typelib $CONDA_ENV_PATH/lib/girepository-1.0/
```

> `CONDA_ENV_PATH` is the location for the Anaconda enviroment, the commented definition is just an example.