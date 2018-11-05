#!/usr/bin/env python3

# Copyright (c) 2016 Stanislav Kontar
# License: MIT

"""
Application used to control XFCE presentation mode in a more convenient way. It is meant to disable
screensaver and all monitor energy saving utilities.

When ran without any parameters it toggles the presentation mode and if the mode ends up being
enabled, it also shows green icon in the system tray.
When ran in automatic mode it shows gray icon in the system tray and monitors system for windows
which satisfy conditions. If it decides to enable presentation mode, the system tray icon changes
to blue.
"""

import argparse
from collections import namedtuple
from os import path
import re
from subprocess import call, check_output
from threading import Thread

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Notify', '0.7')
from gi.repository import GLib, Gtk, Notify


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

COMMAND_PRESENTATION = 'xfconf-query -c xfce4-power-manager -p /xfce4-power-manager/presentation-mode'
COMMAND_XAUTOLOCK = 'xautolock'
COMMAND_NOTIFICATIONS_DND = 'xfconf-query -c xfce4-notifyd -p /do-not-disturb'

WD = path.dirname(path.realpath(__file__))  # Manage to run script anywhere in the path
ICON_GREEN = path.join(WD, 'Hopstarter-Soft-Scraps-Button-Blank-Green.ico')
ICON_GRAY = path.join(WD, 'Hopstarter-Soft-Scraps-Button-Blank-Gray.ico')
ICON_BLUE = path.join(WD, 'Hopstarter-Soft-Scraps-Button-Blank-Blue.ico')

Window = namedtuple('Window',
                    'window_id desktop_id pid client title cpu fullscreen name wm_classes')


def xautolock_set(state):
    """
    Set xautolock to specific state.
    """
    if state:
        call(COMMAND_XAUTOLOCK + ' -enable', shell=True)
    else:
        call(COMMAND_XAUTOLOCK + ' -disable', shell=True)


def presentation_mode_set(state):
    """
    Set xfce4 presentation mode to specific state.
    """
    call(COMMAND_PRESENTATION + ' -s {}'.format(str(state).lower()), shell=True)


def notifications_dnd_set(state):
    """
    Set xfce4 notifications DND to specific state.
    """
    call(COMMAND_NOTIFICATIONS_DND + ' -s {}'.format(str(state).lower()), shell=True)


def presentation_mode_state():
    """
    Read xfce4 presentation mode state.
    """
    result = check_output(COMMAND_PRESENTATION, shell=True)
    if b'false' in result:
        return False
    if b'true' in result:
        return True
    raise RuntimeError('Unknown state')


def enable_presentation_all(auto):
    """
    Enables all functionality needed for true presentation mode.

    When it is done from automatic mode, then notifications are not disabled.
    """
    xautolock_set(False)
    if not auto:
        notifications_dnd_set(True)
    presentation_mode_set(True)


def disable_presentation_all(auto):
    """
    Disables all functionality needed for true presentation mode.

    When it is done from automatic mode, then notifications are not re-enabled.
    """
    xautolock_set(True)
    if not auto:
        notifications_dnd_set(False)
    presentation_mode_set(False)


def get_windows():
    """
    Return all windows found by WM with CPU, fullscreen, process name, and class information.
    """
    # Basic window information
    result = check_output('nice -n 19 wmctrl -l -p', shell=True)
    lines = [a for a in result.decode('utf8').split('\n') if a != '']
    windows = [re.split(r'\s+', a, maxsplit=4) for a in lines]

    # Window properties
    window_index = {}
    for window in windows:
        window_id = window[0]
        r = check_output('nice -n 19 xprop -id {}'.format(window_id), shell=True)
        wm_classes = []
        r_class = re.search(br'WM_CLASS\(STRING\) = (.*)\n', r)
        if r_class:
            wm_classes = re.findall('\"(.*?)\"', r_class.group(1).decode('ascii'))
        fullscreen = b'WM_STATE_FULLSCREEN' in r
        window_index[window_id] = (fullscreen, wm_classes)

    # Basic process information
    usable_lines = []
    result = check_output('nice -n 19 top -b -n 2', shell=True)
    lines = [a for a in result.decode('utf8').split('\n') if a != '']
    first_found = False
    for i, line in enumerate(lines):
        r = re.search(r'PID\s+USER\s+PR\s+NI', line)
        if r:
            if first_found:
                usable_lines = lines[i + 1:]
                break
            else:
                first_found = True
    processes = [re.split(r'\s+', a.strip()) for a in usable_lines]
    process_index = {a[0]: (a[8], a[11]) for a in processes}

    result = []
    for window in windows:
        cpu, name = process_index.get(window[2], (None, None))
        fullscreen, wm_classes = window_index.get(window[0], None)
        result.append(Window(*window, cpu=cpu, fullscreen=fullscreen, name=name,
                             wm_classes=wm_classes))
    return result


class Application:
    def __init__(self, auto=False):
        self.worker_thread = None
        self.counter = 0

        # Status icon
        if auto:
            icon = ICON_GRAY
        else:
            icon = ICON_GREEN
        self.status_icon = Gtk.StatusIcon(file=icon, visible=True)
        if auto:
            tooltip = 'Interval {} minutes'.format(INTERVAL)
            self.status_icon.set_tooltip_text(tooltip)

        # Menu
        self.menu = Gtk.Menu()
        close = Gtk.ImageMenuItem(Gtk.STOCK_QUIT, use_stock=True)
        close.connect('activate', self.on_close, None)
        self.menu.append(close)

        # Callbacks
        self.status_icon.connect('popup-menu', self.on_menu)

        # Start
        if auto:
            GLib.timeout_add_seconds(INTERVAL / CHECKS * 60, self.on_auto_interval)
        else:
            self.on_manual_interval()
            GLib.timeout_add_seconds(1, self.on_manual_interval)

    def on_menu(self, sender, button, time):
        self.menu.show_all()
        self.menu.popup(None, None, Gtk.StatusIcon.position_menu, sender, button, time)

    def on_close(self, widget, event):
        disable_presentation_all(auto=False)
        if self.worker_thread is not None:
            self.worker_thread.join()
        Gtk.main_quit()

    def on_manual_interval(self):
        if not presentation_mode_state():
            self.on_close(None, None)
        return True

    def on_auto_interval(self):
        self.worker_thread = Thread(target=self.worker)
        self.worker_thread.start()
        return True

    def worker(self):
        windows = get_windows()

        trigger_window = None
        reasons = []
        for window in windows:
            for condition in CONDITIONS:
                if 'wm_class' in condition:
                    if condition['wm_class'] not in window.wm_classes:
                        continue
                    else:
                        reasons.append('CLASS = {}'.format(condition['wm_class']))
                if 'fullscreen' in condition:
                    if condition['fullscreen'] != bool(window.fullscreen):
                        continue
                    else:
                        reasons.append('FULLSCREEN')
                if 'cpu' in condition:
                    if float(window.cpu) < condition['cpu']:
                        continue
                    else:
                        reasons.append('CPU = {}'.format(window.cpu))
                trigger_window = window

        tooltip = 'Interval {} minutes'.format(INTERVAL)
        if trigger_window:
            self.counter += 1
            if self.counter > CHECKS:
                self.counter = CHECKS
            message = trigger_window.title + '\n' + ' | '.join(reasons) + ' => ' + str(self.counter)
            tooltip += '\n' + message
            print(message)
        else:
            self.counter -= 1
            if self.counter < 0:
                self.counter = 0
            else:
                message = '=> ' + str(self.counter)
                tooltip += '\n' + message
                print(message)

        if self.counter == CHECKS:
            GLib.idle_add(self.enable_presentation_auto)
        elif self.counter == 0:
            GLib.idle_add(self.disable_presentation_auto)
        self.status_icon.set_tooltip_text(tooltip)

    def enable_presentation_auto(self):
        enable_presentation_all(auto=True)
        self.status_icon.set_from_file(ICON_BLUE)

    def disable_presentation_auto(self):
        disable_presentation_all(auto=True)
        self.status_icon.set_from_file(ICON_GRAY)


if __name__ == '__main__':
    Notify.init('presentation_switch')

    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-a', '--auto', action='store_true', help='enable automatic mode')
    args = parser.parse_args()

    if args.auto:
        app = Application(auto=True)
        Gtk.main()
    else:
        if presentation_mode_state():
            disable_presentation_all(auto=False)

            notification = Notify.Notification.new('Presentation mode OFF', icon=ICON_GRAY)
            notification.set_timeout(1000)
            notification.show()
        else:
            notification = Notify.Notification.new('Presentation mode ON', icon=ICON_GREEN)
            notification.set_timeout(1000)
            notification.show()

            enable_presentation_all(auto=False)

            app = Application()
            Gtk.main()

    disable_presentation_all(auto=False)
