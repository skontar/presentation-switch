# XFCE Presentation Switcher

Application used to control XFCE presentation mode in a more convenient way. It is meant to disable
screensaver and all monitor energy saving utilities.

When ran without any parameters it toggles the presentation mode and if the mode ends up being
enabled, it also shows green icon in the system tray.
When ran in automatic mode it shows gray icon in the system tray and monitors system for windows
which satisfy conditions. If it decides to enable presentation mode, the system tray icon changes
to blue.


## Installation

Prerequisites are `python3` and `python3-gobject` packages, which should be installed on Fedora by
default.

Download the application directory and put it anywhere. Either add `presentations_switch.py --auto`
to your startup script or bind `presentations_switch.py` to a keyboard shortcut.


## Usage

Run `presentations_switch.py` with or without `--auto` option.

    -h, --help  show this help message and exit
    -a, --auto  enable automatic mode (default: False)

To change a way how the automatic mode behaves, you need to update a few constants in the Python
code:

	INTERVAL = 9  # The time interval in minutes in which are checks performed
	CHECKS = 3  # How many times the check needs to be satisfied during that interval for presentation
	            # mode to activate
	# List of conditions, supported flags are:
	# * wm_class - as reported by `xprop`, string value, case sensitive
	# * fullscreen - as reported by `xprop`, bool value
	# * cpu - minimal value as reported by `top`, float value
	# All flags are optional
	CONDITIONS = (
	    dict(wm_class='Firefox', cpu=15.0),
	)

More lines act as logical or, more options act as logical and. Some examples of valid CONDITIONs
would be:

	CONDITIONS = (
	    dict(wm_class='Firefox', fullscreen=True),  # Fullscreen Firefox window
	    dict(wm_class='Vlc', cpu=15.0),             # VLC window using more than 15% CPU according
	                                                # to `top` command
	)


## Testing

It was tested on various Fedora 22 and Fedora 23 desktop systems, mostly XFCE spins.


## Icons artwork

Website: [IconArchive](http://www.iconarchive.com/show/soft-scraps-icons-by-hopstarter.html)
Artist: [Hopstarter (Jojo Mendoza)](http://www.iconarchive.com/artist/hopstarter.html)
License: [CC Attribution-Noncommercial-No Derivate 4.0](http://creativecommons.org/licenses/by-nc-nd/4.0/)

