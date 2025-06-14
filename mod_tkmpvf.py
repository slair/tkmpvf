#!/usr/bin/python3 -u
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Any, Callable, Dict, List, Optional, Union  # noqa:F401

import os
import sys
import random
import glob
import tempfile
import time
import re
import socket
import logging
import subprocess  # nosec
import configparser
import shutil
import gettext
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
import threading

import psutil

# ~ from tinytag import TinyTag
from subprocess import check_output  # nosec

# ~ # pylint:disable=E0611
from transliterate import translit  # , get_available_language_codes

# ~ get_available_language_codes()	 # без этого заменяются языки
import translit_pikabu_lp  # noqa добавляем свой язык
from num2t4ru import num2text  # , num2text_VP
from mod_monitors import enum_display_monitors
import mod_helpertk as htk
from mod_tools import tp, stop  # noqa:F401

import mod_xdotool

try:
	from my_settings import FASTER_KEYWORDS, BRIGHTER_KEYWORDS, add_brightness_list, dont_delete_list, no_hide_window_list
except ModuleNotFoundError:
	FASTER_KEYWORDS = tuple()  # type: ignore[assignment]
	BRIGHTER_KEYWORDS = tuple()  # type: ignore[assignment]
	add_brightness_list = tuple()  # type: ignore[assignment]
	dont_delete_list = tuple()  # type: ignore[assignment]

ope = os.path.exists
opj = os.path.join
tpc = time.perf_counter
_ = gettext.gettext

TS_PORT = 12987
WIN32 = sys.platform == "win32"
LINUX = sys.platform == "linux"
TMPDIR = tempfile.gettempdir()
MIN_ALPHA = 0.25
MAX_ALPHA = 0.75

start_tpc = tpc()


def dp(*args):
	if _DEBUG:
		a1 = args[0]
		bl = ""
		if isinstance(a1, str):
			if a1[0] in "!><-+":
				bl = a1[0]
				# ~ na0 = a1[1:]
				# ~ args = (na0, *args[1:])
		print(bl + "\t%.2f\t" % (tpc() - start_tpc), *args)


VIDEO_EXT = (
	"*.mp4",
	"*.mkv",
	"*.avi",
	"*.webm",
	"*.m4v",
	"*.mov",
	"*.dat",
	"*.3gp",
	"*.unknown_video",
)


def print_unsupported_platform_and_exit(rc=100):
	dp("Unknown platform - %r" % sys.platform)
	sys.exit(rc)


if WIN32:
	from ctypes import windll  # type:ignore[attr-defined]

	timeBeginPeriod = windll.winmm.timeBeginPeriod
	timeBeginPeriod(1)

PLAYER = "mpv"

if WIN32:
	PLAYER += ".exe"

# todo: убрать ahk, трэй бесится, слишком дорого ради одного send_key_to_player
ahk = None
# mypy: disable-error-code="import-not-found,arg-type,var-annotated"
if WIN32:
	from ahk import AHK  # pylint: disable=E0401
	from ahk.window import Window  # pylint: disable=E0401

	ahk = AHK()

video_folder = r"."


def getflag(flags, folder=None):
	flagnames = []
	if isinstance(flags, (list, tuple)):
		flagnames.extend(flags)
	elif isinstance(flags, str):
		flagnames.append(flags)
	else:
		loge("wrong type flags=%r", type(flags))

	for fn in flagnames:
		if folder:
			fp = opj(folder, fn)
		else:
			fp = fn

		if ope(fp):
			return True

	return False


dont_delete_flag = ("~~dont-delete~~", ".~~dont-delete~~")

# todo: brightness value from flag instead *
# ~ add_brightness_flag = "~~add-brightness-*-~~"
add_brightness_flag = ("~~add-brightness~~", ".~~add-brightness~~")

# todo: speed value from flag instead *
# ~ faster_speed_flag = "~~faster-speed-*-~~"
faster_speed_flag = ("~~faster-speed~~", ".~~faster-speed~~")

cd = os.getcwd()
# ~ FASTER_SPEED = cd.endswith("_news")
FASTER_SPEED = False

ADD_BRIGHTNESS = any([a in cd for a in add_brightness_list])

NO_HIDE_WINDOW = any([a in cd for a in no_hide_window_list])

DONT_DELETE = False

for item in dont_delete_list:
	if item in cd:
		DONT_DELETE = True
		break

cd_ = cd
while cd_:
	# ~ print(cd_)
	if getflag(dont_delete_flag, cd_):
		tp(f"{dont_delete_flag!r} found in {cd_!r}")
		DONT_DELETE = True
		break

	last_cd = cd_
	cd_ = os.path.split(cd_)[0]
	if cd_ == last_cd:
		break

if getflag(add_brightness_flag):
	ADD_BRIGHTNESS = True
if getflag(faster_speed_flag):
	FASTER_SPEED = True

TPL_PLAY_CMD = None
PLAYER_BINARY = shutil.which(PLAYER)


def get_TPL_PLAY_CMD():
	if WIN32:
		res = " ".join(
			(
				PLAYER_BINARY,
				"%s",
				"--audio-channels=stereo",
				"--audio-normalize-downmix=yes",
				"--fs-screen=%s",
				"--softvol-max=500",
				"--speed=1.33" if FASTER_SPEED else "",
				"--brightness=16" if ADD_BRIGHTNESS else "",
				"--",
				'"%s"',
			)
		)
	elif LINUX:
		res = " ".join(
			(
				PLAYER_BINARY,
				"%s",
				"--vo=gpu",
				"--audio-channels=stereo",
				"--audio-normalize-downmix=yes",
				"--fs-screen=%s",
				"--volume-max=500",
				"--volume=90",
				"--brightness=16" if ADD_BRIGHTNESS else "",
				"--speed=1.33" if FASTER_SPEED else "",
				"--",
				"'%s'",
			)
		)
	else:
		print_unsupported_platform_and_exit()
		res = None

	return res


_DEBUG = True

FNSEP = "(_!_)"  # FileName SEParator in ini file
FS_CHANGE_STEP = 3  # Font Size CHANGE STEP

sDURATION = "Время"
sDURATION_DESC = "Время ↑"
sDURATION_ASC = "Время ↓"

sFSIZE = "Размер"
sFSIZE_DESC = "Размер ↑"
sFSIZE_ASC = "Размер ↓"

sFN = "FN"
sFN_DESC = "FN ↑"
sFN_ASC = "FN ↓"

sTITLE = "Название"
sTITLE_DESC = "Название ↑"
sTITLE_ASC = "Название ↓"

REPINT_MSEC = 1000
MAX_TIME_TO_DIE = 15.0
TIME_TO_RENAME = 2.0
TIME_TO_START = 0.0
TIME_TO_EXIT = 7.0
PLAY_FINISHED = "play finished"
VIDEO_RENAMED = "video renamed"
PLAYING = "playing"
STOPPED = "stopped"

COLOR_RENAMED_FG_NORM = "#c01000"
COLOR_RENAMED_BG_NORM = "#ffa0a0"
if WIN32:
	COLOR_RENAMED_BG_NORM = os.environ.get("COL_SYSTEMBUTTONFACE", "SystemButtonFace")
elif LINUX:
	COLOR_RENAMED_BG_NORM = os.environ.get("COL_SYSTEMBUTTONFACE", "gray85")

COLOR_RENAMED_FG_FAILED = "#800000"
COLOR_RENAMED_BG_FAILED = "#ffff00"

COLOR_FG_TITLE = "#000080"
COLOR_BG_TITLE = "#808080"
if WIN32:
	COLOR_BG_TITLE = os.environ.get("COL_SYSTEMBUTTONFACE", "SystemButtonFace")
elif LINUX:
	COLOR_BG_TITLE = os.environ.get("COL_SYSTEMBUTTONFACE", "gray85")

PARTSEP = "·"

config = configparser.ConfigParser()
config["global"] = {}
config.my_changed = False  # type:ignore[attr-defined]
pid_fd = None

MY_FILE_NAME = os.path.abspath(__file__)
if os.path.islink(MY_FILE_NAME):
	MY_FILE_NAME = os.readlink(MY_FILE_NAME)
MY_FOLDER = os.path.dirname(MY_FILE_NAME)
MY_NAME = os.path.splitext(os.path.basename(MY_FILE_NAME))[0]


try:
	import saymod
	from saymod import say_async, say, snd_play_async, snd_play, saymod_setup_log, say_with_queue, run_talk_server

	saymod_setup_log(MY_NAME)
except ModuleNotFoundError:

	def say_async(*args, **kwargs):  # noqa
		dp("! say_async(", *args, ")")

	def say(*args, **kwargs):  # noqa
		dp("! say(", *args, ")")

	def snd_play_async(*args, **kwargs):  # noqa
		dp("! snd_play_async(", *args, ")")

	def snd_play(*args, **kwargs):  # noqa
		dp("! snd_play(", *args, ")")


BASELOGFORMAT = "%(message)s"
BASEDTFORMAT = "%d.%m.%y %H:%M:%S"
FLN = "[%(levelname)9s %(asctime)s] %(funcName)s %(filename)s:%(lineno)d "
FLNC = "%(filename)s:%(lineno)d:%(levelname)9s %(asctime)s %(funcName)s "
logger = logging.getLogger(MY_NAME)
logger.setLevel(logging.DEBUG)
logd = logger.debug
logi = logger.info
logw = logger.warning
loge = logger.error
logc = logger.critical

console_output_handler = logging.StreamHandler(sys.stderr)
formatter = logging.Formatter(FLNC + BASELOGFORMAT, BASEDTFORMAT)
console_output_handler.setFormatter(formatter)
logger.addHandler(console_output_handler)

LOG_FILE_NAME = opj(TMPDIR, MY_NAME + ".log")
if _DEBUG:
	tp("LOG_FILE_NAME = %r", LOG_FILE_NAME)

fh = logging.FileHandler(LOG_FILE_NAME, encoding="utf-8")
formatter = logging.Formatter(FLN + BASELOGFORMAT, BASEDTFORMAT)
fh.setFormatter(formatter)
logger.addHandler(fh)

ENV_HOME = os.environ.get("HOME", os.environ.get("USERPROFILE", None))
if ENV_HOME is None:
	loge("No HOME or USERPROFILE environment variable")

XDG_DATA_HOME = os.environ.get("XDG_DATA_HOME", os.environ.get("APPDATA", opj(ENV_HOME, opj(".local", "share"))))  # type:ignore[arg-type]

MY_XDG_DATA_HOME = opj(XDG_DATA_HOME, MY_NAME)
if not os.path.exists(MY_XDG_DATA_HOME):
	logi("Create folder %r", MY_XDG_DATA_HOME)
	os.makedirs(MY_XDG_DATA_HOME)

XDG_CONFIG_HOME = os.environ.get("XDG_CONFIG_HOME", os.environ.get("LOCALAPPDATA", opj(ENV_HOME, ".config")))  # type:ignore[arg-type]

MY_XDG_CONFIG_HOME = opj(XDG_CONFIG_HOME, MY_NAME)
if not os.path.exists(MY_XDG_CONFIG_HOME):
	logi("Create folder %r", MY_XDG_CONFIG_HOME)
	os.makedirs(MY_XDG_CONFIG_HOME)

CONFIG_FILE_PATH = opj(MY_XDG_CONFIG_HOME, MY_NAME + ".ini")

SND_FOLDER = opj(ENV_HOME, "share", "sounds")  # type:ignore[arg-type]
SND_CLICK = opj(SND_FOLDER, "click-06.wav")
SND_DRUM = opj(SND_FOLDER, "drum.wav")

# note: кэш, чтобы не сканировать файлы каждый раз
dur_cache = dict()  # type:ignore[var-annotated]
dur_cache_changed = False

DUR_CACHE_FN = "%s-dur-cache.txt" % MY_NAME
DUR_CACHE_FP = opj(TMPDIR, DUR_CACHE_FN)

MAX_DURATION = 7 * 24 * 60 * 60  # неделя в секундах

if WIN32:
	mi_bin = shutil.which("MediaInfo.exe")
elif LINUX:
	mi_bin = shutil.which("mediainfo")
else:
	mi_bin = None

if not mi_bin:
	dp("! MediaInfo not found!")
	sys.exit(100)

run_talk_server()


def save_cache(fp: str, cache: dict, datasep: str = "|"):
	global dur_cache_changed
	if not dur_cache_changed:
		return

	with open(fp, "w", encoding="utf-8", newline="\n") as handle:
		logi("Dumping %d items to %r", len(cache), fp)
		# ~ json.dump(cache, handle, ensure_ascii=False, indent=4)
		res = ""
		for k, v in cache.items():
			res += "%s%s%s\n" % (k, datasep, v)
		handle.write(res)
		dur_cache_changed = False


def load_cache(fp: str, datasep: str = "|") -> dict:
	global dur_cache_changed
	with open(fp, "r", encoding="utf-8", newline="\n") as handle:
		# ~ res = json.load(handle)
		res = dict()
		fc = handle.read()
		for line in fc.split("\n"):
			data = line.split(datasep)
			if data[0]:
				res[data[0]] = float(data[1])
		logi("Read %d items from %r", len(res), fp)
		dur_cache_changed = False
	return res


def fix2title(s: str) -> str:
	res = s.replace("\r", " ")
	res = res.replace("\n", " ")
	res = res.replace("\t", " ")
	while "  " in res:
		res = res.replace("  ", " ")
	return res


def get_duration(fp) -> tuple[Any, int]:
	global dur_cache, dur_cache_changed
	if ope(fp):
		fstat = os.stat(fp)
		cfp = "%s %s %s %s" % (fp, fstat.st_size, fstat.st_ctime, fstat.st_mtime)
		if cfp in dur_cache:
			duration = dur_cache[cfp]
		else:
			if WIN32:
				si = subprocess.STARTUPINFO()  # type:ignore[attr-defined]
				si.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type:ignore[attr-defined]
				# si.wShowWindow = subprocess.SW_HIDE # default
				try:
					sduration = str(
						check_output(f'"{mi_bin}" --Inform="Video;%Duration%" "{fp}"', shell=False, startupinfo=si),  # nosec
						encoding="utf-8",
					)

					if "." in sduration:
						duration = int(sduration.split(".", maxsplit=1)[0])
					else:
						duration = int(sduration)

					duration /= 1000

					if duration > MAX_DURATION:
						logw("Wrong duration=%r, fp=%r changed to %r", duration, fp, 0)
						duration = 0

					dur_cache[cfp] = duration
					if not dur_cache_changed:
						dur_cache_changed = True
				except ValueError as e:
					loge("fp=%r, e=%r", fp, e)
					duration = 0
					logw("Cant get fp=%r duration, changed to %r", fp, 0)

			elif LINUX:
				try:
					sduration = str(
						check_output(f'"{mi_bin}" --Inform="Video;%Duration%" \'{fp}\'', shell=True),  # nosec
						encoding="utf-8",
					)
					# ~ , shell=False, startupinfo=si))  # nosec

					if "." in sduration:
						duration = int(sduration.split(".", maxsplit=1)[0])
					else:
						duration = int(sduration)

					duration /= 1000

					if duration > MAX_DURATION:
						logw("Wrong duration=%r, fp=%r changed to %r", duration, fp, 0)
						duration = 0

					dur_cache[cfp] = duration
					if not dur_cache_changed:
						dur_cache_changed = True
				except subprocess.CalledProcessError as e:
					loge("fp=%r, e=%r", fp, e)
					duration = 0
					logw("Cant get fp=%r duration, changed to %r", fp, 0)
				except ValueError as e:
					loge("fp=%r, e=%r", fp, e)
					duration = 0
					logw("Cant get fp=%r duration, changed to %r", fp, 0)

		return duration, 0

	return 0, 0


logi("Starting ")
logd("add_brightness=%r, add_brightness_list=%r", ADD_BRIGHTNESS, add_brightness_list)
logd("DONT_DELETE=%r, DONT_DELETE_list=%r", DONT_DELETE, dont_delete_list)


def my_tk_excepthook(*args):
	logc("\n! args=%r", args, exc_info=args)
	# ~ logc("args= %r", args, exc_info=args)

	pid_fp = os.path.join(TMPDIR, os.path.basename(__file__) + ".pid")
	if os.path.exists(pid_fp):
		if pid_fd:
			pid_fd.close()
		try:
			os.unlink(pid_fp)
			logd("Deleted %r", pid_fp)
		except PermissionError as e:
			logw("Deleting %r failed. %r", pid_fp, e)

	EXIT()


sys.excepthook = my_tk_excepthook
tk.Tk.report_callback_exception = my_tk_excepthook


def load_config():
	if os.path.exists(CONFIG_FILE_PATH):
		logi("Reading %r", CONFIG_FILE_PATH)
		config.read(CONFIG_FILE_PATH, encoding="utf-8")
	else:
		logw("File %r not found", CONFIG_FILE_PATH)
	config.my_changed = False


def save_config():
	if config.my_changed:
		with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
			logi("Writing %r", CONFIG_FILE_PATH)
			config.write(f)
		config.my_changed = False


def change_config(section, option, value):
	if not isinstance(value, str):
		value = str(value)

	old_value = config[section].get(option)
	if old_value != value:
		logd("Change [%r][%r] from %r to %r", section, option, old_value, value)

		config[section][option] = value
		config.my_changed = True
	return config.my_changed


def all_children(wid):
	_list = wid.winfo_children()

	for item in _list:
		if item.winfo_children():
			_list.extend(item.winfo_children())

	return _list


def mod_color(color, val):
	r = int(color[1:3], 16) + val
	g = int(color[3:5], 16) + val
	b = int(color[5:7], 16) + val
	if r > 255:
		r = 255  # noqa
	if g > 255:
		g = 255  # noqa
	if b > 255:
		b = 255  # noqa
	return "#%x%x%x" % (r, g, b)


def lighter(color, val=16):
	return mod_color(color, val)


def darker(color, val=16):
	return mod_color(color, -val)


def sizeof_fmt(num):
	for x in ["B ", "kB", "MB", "GB", "TB"]:
		if num < 1024.0:
			return "%3.1f %s" % (num, x)
		num /= 1024.0


def untranslit_word(w):
	# ~ r = translit(w, "ru")
	r = translit(w, "pikabu.ru")
	return r


def untranslit(s):
	res = []
	words = s.split()
	for word in words:
		res.append(untranslit_word(word))
	res = " ".join(res)
	if res:
		return res[0].upper() + res[1:]
	else:
		return res


serverSocket = None


def already_running(UDP_PORT: int, log: Union[Callable, None] = None) -> Union[bool, None]:
	res = None
	if WIN32:
		import win32event  # pylint: disable=E0401
		import win32api  # pylint: disable=E0401
		from winerror import ERROR_ALREADY_EXISTS  # pylint: disable=E0401

		mutex = win32event.CreateMutex(None, False, MY_NAME)  # noqa:F841
		last_error = win32api.GetLastError()
		if last_error == ERROR_ALREADY_EXISTS:
			res = True

	elif LINUX:
		global serverSocket
		serverSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		try:
			serverSocket.bind(("", UDP_PORT))
			res = False
		except OSError as e:
			if e.errno == 98:
				res = True
			else:
				if log:
					log("e=%s" % e)
				res = False
	else:
		raise NotImplementedError("Unknown platform %r" % sys.platform)

	return res


def get_video_title(s):
	if os.sep in s:
		s = os.path.basename(s)

	# ~ s = strip_above_0xffff(s)

	if "Й" in s:
		s = s.replace("Й", "Й")
	if "й" in s:
		s = s.replace("й", "й")

	ls = s.lower()
	if (
		ls.endswith(".mp4")
		or ls.endswith(".avi")
		or ls.endswith(".mov")
		or ls.endswith(".mkv")
		or ls.endswith(".m4v")
		or ls.endswith(".dat")
	):
		s = s[:-4]
	elif ls.endswith(".webm"):
		s = s[:-5]
	elif ls.endswith(".unknown_video"):
		s = s[:-14]

	if " - " in s:
		s = s.replace(" - ", "\n")

	if " _ " in s:
		s = s.replace(" _ ", "\n")

	if "_" in s:
		s = s.replace("_", " ")

	s = re.sub(" +", " ", s)

	if "." in s:
		s = s.replace(".", " ")

	s = s.strip()

	channel = None

	if s.count(PARTSEP) == 3:
		dt, channel, title, _ = s.split(PARTSEP)
		title = re.sub(r"(?<=\d)[_](?=\d)", ":", title)

	elif s.count(PARTSEP) == 2:
		_na = "NA"
		dt, title, _ = s.split(PARTSEP)
		title = re.sub(r"(?<=\d)[_](?=\d)", ":", title)
		# ~ loge("\n! s=%r, dt=%r, title=%r", s, dt, title)
		_pnap = PARTSEP + _na + PARTSEP
		if title == _na and s.startswith(_pnap):
			title = s[len(_pnap) :].strip()
		# ~ loge("\n< s=%r, dt=%r, title=%r", s, dt, title)

	elif s.count(PARTSEP) == 1:
		dt, title = s.split(PARTSEP)
		if " " in dt:
			title = dt
		else:
			title = title[: title.rfind(".")]
			if title.split()[-1].isdigit():
				title = title[: title.rfind(" ")]

	else:
		title = s

	if title.endswith("yapfiles ru") and title != "yapfiles ru":
		title = untranslit(title[:-11])

	if channel and channel not in ("NA",):
		return channel + "\n" + title

	return title


ann_prefixes = (
	"Найдено",
	"Обнаружено",
	"Будем смотреть",
	"Тут подвезли",
	"Позырим, что нового",
	"Ух т^ыы!",
	"Ч^о тут у нас?",
)
ann_suffixes = (
	("вид^ос", "вид^оса", "вид^осов"),
	("ролик", "ролика", "роликов"),
	("видео", "видео", "видео"),
)
narrators = ("Aleksandr", "Artemiy", "Elena", "Irina", "Pavel")


def duration_fmt(duration):
	dur_sec = duration[0]

	# ~ if dur_sec > 1000000000000:
	# ~ sys.exit()

	try:
		res = str(timedelta(seconds=dur_sec))
	except Exception as e:
		loge("duration=%r, dur_sec=%r", duration, dur_sec, exc_info=e)
		return "n/a"

	if "." in res:
		res = res.split(".", maxsplit=1)[0]

	if res.startswith("0:"):
		res = res[2:]

	if res.startswith("00:"):
		res = res[3:]

	return res


def td2words(td_object):
	if not isinstance(td_object, timedelta):
		return td_object

	seconds = int(td_object.total_seconds())
	if seconds < 0:
		seconds = abs(seconds)
	periods = [
		(("год", "года", "лет"), 60 * 60 * 24 * 365, "m"),
		(("месяц", "месяца", "месяцев"), 60 * 60 * 24 * 30, "m"),
		(("день", "дня", "дней"), 60 * 60 * 24, "m"),
		(("час", "час^а", "часов"), 60 * 60, "m"),
		(("минута", "минуты", "минут"), 60, "f"),
		(("секунда", "секунды", "секунд"), 1, "f"),
	]

	strings = []
	for period_name, period_seconds, gender in periods:
		if seconds >= period_seconds:
			period_value, seconds = divmod(seconds, period_seconds)
			period_value_str = num2text(period_value, (period_name, gender))
			strings.append("%s" % period_value_str)
	if strings:
		return " ".join(strings)
	else:
		return ""


def get_pids_by_fn(fn):
	res = []
	proc_iter = psutil.process_iter(attrs=["pid", "name", "cmdline"])
	for p in proc_iter:
		if p.info["cmdline"] and fn in p.info["cmdline"]:
			res.append(p.pid)
	return res


def do_command_bg(cmd):
	proc = None
	if WIN32:
		bshell = False
		proc = subprocess.Popen(
			cmd,
			shell=bshell,
			stdin=subprocess.PIPE,  # nosec
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
		)
	elif LINUX:
		bshell = True
		proc = subprocess.Popen(cmd + ">> /tmp/mpv.log 2>&1 &", shell=bshell)  # nosec  # pylint: disable=
	else:
		print_unsupported_platform_and_exit()
	return proc


class Splash(tk.Frame):
	window_width = 512
	window_height = 128
	working = True

	def __init__(self, master=None):
		super().__init__(master)
		self.master = master
		self.pack(side="top", fill=tk.BOTH, expand=True)
		self._title = "Загрузка...    "
		self.master.title(self._title)

		self.master.bind("<KeyPress>", self.on_keypress)
		self.bind("<KeyPress>", self.on_keypress)

		self.l_fn = tk.Label(self.master, text="<filename>", height=3)
		self.l_fn.bind("<Configure>", lambda e: self.l_fn.config(wraplength=self.l_fn.winfo_width()))
		self.l_fn.pack(side="top", fill=tk.BOTH, expand=True, ipadx=4, ipady=2, padx=4)

		self.l_progress = tk.Label(self.master, text="<progress>")
		self.l_progress.pack(side="bottom", fill=tk.BOTH, expand=True, ipadx=4, ipady=2)

		self.pb = ttk.Progressbar(self.master, orient=tk.HORIZONTAL, length=100, mode="determinate")
		self.pb.pack(side="bottom", fill="x", expand=False, padx=4)

		# ~ xpos = (self.master.winfo_screenwidth() - self.window_width) // 2
		# ~ ypos = (self.master.winfo_screenheight() - self.window_height) // 2
		# ~ self.master.geometry("%sx%s+%s+%s" % (
		# ~ self.window_width, self.window_height, xpos, ypos))
		htk.random_appearance(self.master, win_size=(self.window_width, self.window_height))

	def on_keypress(self, e):
		if e.keysym == "Escape":
			self.working = False
			htk.random_disappearance(self.master)
			self.master.destroy()


def EXIT(rc=0):
	# done: Сохранение настроек
	save_config()
	save_cache(DUR_CACHE_FP, dur_cache)
	# note: wait for all threads to complete
	threads = None
	while not threads or len(threads) > 1:
		threads = threading.enumerate()
		# ~ logd("%r", " ".join(t.name for t in threads))
	logi("Exiting rc=%r\n\n\n\n\n\n\n\n", rc)
	sys.exit(rc)


def get_random_color():
	if _DEBUG:
		r = random.randint(0, 255) // 16 * 16  # nosec
		g = random.randint(0, 255) // 16 * 16  # nosec
		b = random.randint(0, 255) // 16 * 16  # nosec
		return "#%02x%02x%02x" % (r, g, b)
	else:
		return None


def fix_filename(fn: str) -> str:
	res = fn
	escape_chars = "!'()"
	changed = None

	for c in escape_chars:
		if c in res:
			# ~ res = res.resplace(c, "\\" + c)
			res = res.replace(c, "")
			changed = True

	if changed:
		logd("%r -> %r", fn, res)
		os.rename(fn, res)
	return res


def wait_for_said(_cb=None):
	q = os.listdir(saymod.TS_QUEUE_FOLDER)
	while q:
		# ~ logd("Waiting os.listdir(saymod.TS_QUEUE_FOLDER)=%r", q)
		if _cb:
			_cb()
		time.sleep(0.1)
		q = os.listdir(saymod.TS_QUEUE_FOLDER)

	while saymod.TS_BUSY:
		# ~ logd("Waiting saymod.TS_BUSY=%r", saymod.TS_BUSY)
		if _cb:
			_cb()
		time.sleep(0.1)


def on_start_video(fp):
	global FASTER_SPEED, ADD_BRIGHTNESS
	# ~ stop("fp=%r", fp)
	fpl = fp.lower()

	ADD_BRIGHTNESS = any([a in cd for a in add_brightness_list])

	for kw in FASTER_KEYWORDS:
		if kw in fpl:
			FASTER_SPEED = True
			break

	for kw in BRIGHTER_KEYWORDS:
		if kw in fpl:
			ADD_BRIGHTNESS = True
			break

	logd("ADD_BRIGHTNESS=%r, FASTER_SPEED=%r, cd=%r", ADD_BRIGHTNESS, FASTER_SPEED, cd)


class Application(tk.Frame):
	my_state = None
	player_pid = None
	video_folder = video_folder
	_palette = {
		"SystemWindow": "#dac9bf",
		# ~ "SystemWindow" : SystemButtonFace,
	}
	sort_by = None
	videos = []
	first_run = True
	skipped = set()
	lStatus_font = ("Impact", 48)
	lVideoTitle_font = ("Impact", 48)
	need_to_exit = False
	ready = False
	end_title = ""
	tpl_title = "%s"
	tpl_title_paused = "paused - %s"
	paused = False
	hover = True
	normal_pos = None

	KP_Enter_pressed = tpc()
	not_announced = True

	def __init__(self, master=None, sort_by="fsize_desc"):
		super().__init__(master)
		# ~ logd("sort_by=%r", sort_by)

		# если сами задумаем выйти после последнего видоса
		self.exit_by_self = False

		self.sort_by = sort_by
		self.master = master
		# todo: надо что-то делать
		# ~ self.master.overrideredirect(True)
		# ~ self._base_title = "tkmpvf - %s" % os.getcwd()
		self._base_title = self.tpl_title
		# ~ self.master.title(self._base_title)
		self.pack(side="top", fill="both", expand=True)
		self.monitors = enum_display_monitors(taskbar=False)
		self.display_names = ["%sx%s" % (item[2], item[3]) for item in self.monitors]

		self.create_widgets()

		self.master.bind("<KeyRelease>", self.on_keyup)
		self.master.protocol("WM_DELETE_WINDOW", self.on_close_master)
		# ~ self.master.bind('<Enter>'
		# ~ , lambda *args: logd("<Enter> args=%r", args))
		# ~ self.master.bind('<Leave>'
		# ~ , lambda *args: logd("<Leave> args=%r", args))

		self.master.bind("<Enter>", self.on_start_hover)
		self.master.bind("<Leave>", self.on_end_hover)

		self.master.bind("<FocusIn>", self.on_focus_in)
		self.master.bind("<FocusOut>", self.on_focus_out)

		self.master.focus_set()
		self.b_skip.focus_set()

		self.my_state = VIDEO_RENAMED
		self.my_state_start = 1

		if "global" in config and "skipped" in config["global"]:
			skipped_items = config["global"]["skipped"].split(FNSEP)
			# ~ logd("skipped_items= %r", skipped_items)
			# ~ logd("any(skipped_items)= %r", any(skipped_items))
			if any(skipped_items):
				self.prop_skipped = set(skipped_items)
		else:
			self.prop_skipped = set()

		logi("len(self.prop_skipped)=%r", len(self.prop_skipped))

		logd("Starts in %r, self.sort_by=%r", os.getcwd(), self.sort_by)

		htk.hide_window(self.master)
		self.master.geometry("+5000+5000")
		self.master.update()
		self.master.withdraw()

		geometry = config["global"].get("normal_geometry", None)
		if geometry is not None:
			tp("geometry=%r", geometry)
			if "-" in geometry:
				geometry = "960x1025+2239+0"
			self.to_ = htk.geometry2list(geometry)
			self.to_.append(1.1)  # alpha

		self.update_idletasks()
		self.on_every_second()
		self.wid = mod_xdotool.win_active()
		normal_geometry = config["global"].get("normal_geometry", None)
		normal_geometry = None
		if normal_geometry is None:
			normal_geometry = "960x1025+2240+0"
			change_config("global", "normal_geometry", normal_geometry)
			save_config()
		self.normal_pos = htk.geometry2tuple(normal_geometry)
		self.hidden_pos = list(self.normal_pos[:])
		self.hidden_pos[0] += self.normal_pos[2] - 16
		self.hidden_pos[1] += self.normal_pos[3] - 16
		logd("\n< self.normal_pos=%r, self.hidden_pos=%r, self.wid=0x%0x", self.normal_pos, self.hidden_pos, self.wid)
		# ~ self.on_hover_change(True)
		htk.anim_window(self.master, (*htk.geometry2tuple(self.master.geometry()), MIN_ALPHA), (*self.normal_pos, MAX_ALPHA))
		self.ready = True

	def on_hover_change(self, _hover=None):
		if not self.ready:
			return

		current_pos = htk.geometry2tuple(self.master.geometry())
		logd("current_pos=%r", current_pos)
		if _hover:
			# возврат в нормальную позицию
			self.ready = False
			self.hover = True
			self.master.attributes("-topmost", True)
			logd(f"showing from {current_pos!r} to {self.normal_pos!r}")
			self.bring_to_front()
			# ~ self.master.overrideredirect(False)
			htk.anim_window(self.master, (*current_pos, MIN_ALPHA), (*self.normal_pos, MAX_ALPHA), bounce=False)
			self.ready = True
		else:
			# скрываем окно
			self.ready = False
			self.hover = False
			self.master.attributes("-topmost", True)
			logd(f"hiding from {current_pos} to {self.hidden_pos!r}")

			if NO_HIDE_WINDOW:
				# остаёмся на месте
				htk.anim_window(self.master, (*current_pos, MAX_ALPHA), (*current_pos, MIN_ALPHA), bounce=False)
				self.master.attributes("-topmost", False)
			else:
				htk.anim_window(self.master, (*current_pos, MAX_ALPHA), (*self.hidden_pos, MIN_ALPHA), bounce=False)

			self.master.update_idletasks()
			self.ready = True

	def on_focus_in(self, e=None):
		logd("e=%r", e)
		if not self.ready:
			return

		# ~ logd("e=%r", e)

	def on_focus_out(self, e=None):
		logd("e=%r", e)
		if not self.ready:
			return

		if self.hover:
			self.hover = False
			# ~ logd("e=%r", e)
			self.after(500, lambda x=None: self.on_hover_change(self.hover))
			# ~ self.on_hover_change(self.hover)

	def on_start_hover(self, e=None):
		if not self.ready:
			return

		if not self.hover:
			self.hover = True
			# ~ logd("e=%r", e)
			self.on_hover_change(self.hover)

	def on_end_hover(self, e=None):
		if not self.ready:
			return

		# ~ if self.hover:
		# ~ self.hover = False
		# ~ logd("e=%r", e)

	def geometry_to_config(self):
		g = self.master.geometry()
		# ~ logd("g=%r", g)
		if not g.startswith("1x1+"):
			change_config("global", "geometry", g)

	def ask_for_delete(self):
		seen_files = glob.glob("*.seen")
		if seen_files:
			if DONT_DELETE:
				say_async("Не буду удалять файлы из этого каталога")
				return

			if int(self.i_delseen.get()) == 1 or messagebox.askyesnocancel(
				"Просмотренные файлы", "Удалить просмотренные файлы?"
			):
				cwd = os.getcwd()
				logd("cwd=%r", cwd)
				for item in seen_files:
					if not cwd.endswith("tkmpvf"):
						logw("Deleting %r", item)
						os.unlink(item)

	def on_close_master(self, *args, **kwargs):  # noqa
		if not self.ready:
			return

		self.ready = False
		self.need_to_exit = True
		self.stop_player()
		self.geometry_to_config()
		self.ask_for_delete()
		htk.random_disappearance(self.master)
		self.master.destroy()

	def refresh(self):
		self.lClock["text"] = datetime.now().strftime("%H:%M:%S")
		self.update()
		self.update_idletasks()

	def start_video(self):
		global FASTER_SPEED, ADD_BRIGHTNESS
		self.fp_video = None
		while not self.fp_video and self.videos:
			self.fp_video, title, fsize, duration = self.videos.pop(0)
			if self.fp_video in self.prop_skipped:
				self.fp_video = None

		# ~ if "'" in self.fp_video:
		# ~ self.fp_video = self.fp_video.replace("'", "\\'")

		self.sort_videos(self.first_run)
		# ~ logd("self.fp_video=%r", self.fp_video)
		# ~ logd("self.player_pid=%r", self.player_pid)
		self.lVideoTitle["text"] = title
		self.lVideoTitle["fg"] = COLOR_FG_TITLE
		self.lVideoTitle["bg"] = COLOR_BG_TITLE
		count_videos = len(self.videos)
		if count_videos:
			self.lStatus["text"] = "Осталось %s %s" % (count_videos, "video")
		else:
			self.lStatus["text"] = "Последнее video"
			self.i_exit.set(True)
			self.exit_by_self = True  # сами назначили выход
			self.i_delseen.set(True)

		# note: ждёт без нарисованных интерфейсов, пока не произнесёт фразы
		wait_for_said(lambda: self.refresh())

		on_start_video(self.fp_video)

		_cmd = get_TPL_PLAY_CMD() % (
			"-fs" if self.i_fullscreen.get() == 1 else "",
			self.display_names.index(self.sv_player_display.get()),
			self.fp_video,
		)
		logd("_cmd=%r", _cmd)
		p = do_command_bg(_cmd)
		self.player_pid = p.pid
		FASTER_SPEED = False
		ADD_BRIGHTNESS = False

	def bring_to_front(self):
		if self.i_bring_to_front.get() == 1:
			self.master.state("normal")
			self.b_skip.focus_force()
			self.master.lift()
			# ~ self.master.after_idle(self.master.attributes, '-topmost', False)

	def change_label_height(self, label, min_height, max_height):
		label_height = label.winfo_height()  # 326
		label_font = label["font"]  # Impact 48
		label_font_name, label_font_size = label_font.rsplit(maxsplit=1)

		label_font_size = int(label_font_size)

		if label_height > max_height:
			label_font_size -= FS_CHANGE_STEP
			label["font"] = (label_font_name, label_font_size)

		elif label_height < min_height:
			label_font_size += FS_CHANGE_STEP
			label["font"] = (label_font_name, label_font_size)

	def on_every_second(self):
		# ~ self.update()
		if not self.ready:
			self.after(REPINT_MSEC, self.on_every_second)
			return

		_start = tpc()
		# ~ logd("self.my_state=%r, duration=%r"
		# ~ , self.my_state, tpc()-self.my_state_start)

		now = datetime.now()
		try:
			self.lClock["text"] = now.strftime("%H:%M:%S")
		except Exception as e:  # noqa
			# ~ if _DEBUG:
			# ~ loge("error", exc_info=e)
			self.splash.working = None
			logd("self.splash.working=%r", self.splash.working)
			htk.random_disappearance(self.splash.master)
			self.splash.master.destroy()
			self.after(REPINT_MSEC, self.on_every_second)
			return
			# ~ self.master.deiconify()

		# приведём title в порядок
		if not self.paused:
			self._base_title = self.tpl_title % fix2title(self.lVideoTitle["text"])
		else:
			self._base_title = self.tpl_title_paused % fix2title(self.lVideoTitle["text"])

		title = self._base_title + self.end_title
		# ~ logd("self._base_title=%r, self.end_title=%r"
		# ~ , self._base_title, self.end_title)
		self.master.title(title)

		self.change_label_height(self.lVideoTitle, min_height=100, max_height=200)

		if self.player_pid and self.my_state == PLAYING:
			self.b_pause["state"] = "normal"
			self.b_skip["state"] = "normal"
			# ~ if not psutil.pid_exists(self.player_pid):
			if not get_pids_by_fn(self.fp_video):
				self.player_pid = None
				self.b_pause["state"] = "disabled"
				self.b_skip["state"] = "disabled"
				self.my_state = PLAY_FINISHED
				self.my_state_start = tpc()
				self._points_added = 0
				# ~ if not NO_HIDE_WINDOW:
				self.on_hover_change(True)
				# ~ self.bring_to_front()

		if self.my_state == PLAY_FINISHED:
			if tpc() - self.my_state_start > (TIME_TO_RENAME + 1.0) and self._points_added >= TIME_TO_RENAME:
				if self.fp_video and self.fp_video not in self.prop_skipped and os.path.exists(self.fp_video):
					rename_status = "<переименовано>"
					color_fg_renamed = COLOR_RENAMED_FG_NORM
					color_bg_renamed = COLOR_RENAMED_BG_NORM

					try:
						os.rename(self.fp_video, self.fp_video + ".seen")
					except PermissionError:
						rename_status = "<не удалось переименовать>\nнет прав"
						color_fg_renamed = COLOR_RENAMED_FG_FAILED
						color_bg_renamed = COLOR_RENAMED_BG_FAILED
					except FileExistsError:
						rename_status = "<не удалось переименовать>\nтакой файл уже есть"
						color_fg_renamed = COLOR_RENAMED_FG_FAILED
						color_bg_renamed = COLOR_RENAMED_BG_FAILED

					fp_name, ext = os.path.splitext(self.fp_video)
					vtt_fp = fp_name + ".ru.vtt"
					if os.path.exists(vtt_fp):
						try:
							os.rename(vtt_fp, vtt_fp + ".seen")
						except PermissionError:
							rename_status = "<vtt не удалось переименовать>\nнет прав"
							color_fg_renamed = COLOR_RENAMED_FG_FAILED
							color_bg_renamed = COLOR_RENAMED_BG_FAILED
						except FileExistsError:
							rename_status = "<vtt не удалось переименовать>\nтакой файл уже есть"
							color_fg_renamed = COLOR_RENAMED_FG_FAILED
							color_bg_renamed = COLOR_RENAMED_BG_FAILED

					self.lVideoTitle["text"] = rename_status
					self.lVideoTitle["fg"] = color_fg_renamed
					self.lVideoTitle["bg"] = color_bg_renamed

				self.my_state = VIDEO_RENAMED
				self.my_state_start = tpc()
				self.after(REPINT_MSEC, self.on_every_second)
				return

			if self._points_added <= TIME_TO_RENAME:
				self.lVideoTitle["text"] += "."
				self._points_added += 1

		elif self.my_state == VIDEO_RENAMED:
			if tpc() - self.my_state_start > TIME_TO_START:
				# ~ if int(self.i_exit.get()) == 0:
				self.get_videos(self.first_run)
				# ~ logd("len(self.videos)=%r self.first_run=%r"
				# ~ , len(self.videos), self.first_run)

				if self.videos and int(self.i_exit.get()) == 0:
					self.sort_videos(self.first_run)
					if self.first_run:
						self.first_run = None
						self.splash.working = None
						logd("self.splash.working=%r", self.splash.working)
						htk.random_disappearance(self.splash.master)
						self.splash.master.destroy()
						self.master.deiconify()
						# ~ logd("self.splash.working=%r", self.splash.working)
						# ~ logd("\n! start appearance")
						# note: show window
						htk.random_appearance_to(self.master, self.to_, duration=0.2)
						# ~ logd("\n! stop appearance")
					if not self.paused:
						self.start_video()
						self.my_state = PLAYING
						self.my_state_start = tpc()
				else:
					self.my_state = STOPPED
					self.my_state_start = tpc()
					# ~ self.clear_lb_videos()

		elif self.my_state == STOPPED:
			if not self.need_to_exit:
				snd_play_async(SND_CLICK)
				state_duration = tpc() - self.my_state_start

				self.lVideoTitle["text"] = "выход через %.1f" % (TIME_TO_EXIT - state_duration)

				self.lStatus["text"] = "Нет video"
				if state_duration > TIME_TO_EXIT:
					snd_play(SND_DRUM, ep=True)
					# ~ self.master.destroy()
					self.on_close_master()

		_duration = tpc() - _start
		if _duration * 1000 > REPINT_MSEC:
			logw("_duration=%r", _duration)

		self.after(REPINT_MSEC, self.on_every_second)

	def send_key_to_player(self, key):
		# ~ logd("ahk=%r, self.player_pid=%r", ahk, self.player_pid)
		if ahk and self.player_pid:
			ahk_pid = "ahk_pid %s" % self.player_pid
			self.win_player = ahk.win_get(title=ahk_pid)
			# ~ logd("ahk_pid=%r, self.win_player=%r", ahk_pid, self.win_player)
			# ~ self.win_player = Window.from_pid(ahk
			# ~ , pid=str(self.player_pid))
			if self.win_player:
				logd("Send %r to %r", key, self.win_player)
				self.win_player.send(key)
				return True
		return False

	def on_keyup(self, e):
		if not self.ready:
			return

		logd("e=%r", e)

		if e.keysym == "Escape":
			self.on_close_master()
		elif e.keysym == "F12":
			self.i_exit.set(not self.i_exit.get())
			self.i_delseen.set(not self.i_delseen.get())
			logd("self.i_exit.get()=%r", self.i_exit.get())
		else:
			if e.keysym == "KP_Enter" or e.keysym == "Return":
				passed = tpc() - self.KP_Enter_pressed
				logd("passed=%r", passed)
				if passed < 0.1:
					logw("KP_Enter залип!")
					if self.not_announced:
						say_with_queue("у вас Кнопка залипла. Завершаю работу", narrator=random.choice(narrators))  # nosec
						self.not_announced = False
					self.i_exit.set(True)
					self.i_delseen.set(False)
				self.KP_Enter_pressed = tpc()

			elif e.keysym == "Pause":
				self.paused = not self.paused

			else:
				logd("e=%r", e)

	def get_videos(self, announce=None):
		folder = self.video_folder
		# ~ logd("os.getcwd()= %r", os.getcwd())
		# ~ self.videos.clear()

		_ = []
		for ext in VIDEO_EXT:
			_ += glob.glob(opj(folder, ext))
			_ += glob.glob(opj(folder, ext.upper()))

		# ~ logd("len(_)=%r", len(_))

		if announce:
			count_videos = len(_)
			if count_videos > 0:
				self.splash = Splash(tk.Tk())
				suffix = random.choice(ann_suffixes)  # nosec
				numsuf = num2text(count_videos, (suffix, "m"))  # .split()
				narrator = random.choice(narrators)  # nosec
				self.splash.l_fn["text"] = ""
				self.splash.l_progress["text"] = ""
				self.update_splash()
				say_with_queue(numsuf, narrator=narrator)
			else:
				say_async("А здесь нет вид^осов", narrator=random.choice(narrators))  # nosec
				# ~ self.bring_to_front()

		# ~ dp("> checking for deleted videos")
		# ~ logd("self.videos=%r", self.videos)
		for i, video_struct in enumerate(self.videos):
			if video_struct[0] not in _:
				logd("deleting %r %r", i, video_struct)
				del self.videos[i]
		# ~ logd("self.videos=%r", self.videos)

		# ~ dp("> checking for added videos")
		fn_count = 0
		fn_total = len(_)
		_duration = 0
		_fsize = 0
		for fn in _:
			fn = fix_filename(fn)

			if fn in self.prop_skipped:
				continue

			# считаем без self.prop_skipped, градусник не доходит до 100%
			fn_count += 1

			if not any(e[0] == fn for e in self.videos):
				# ~ dp("! adding", fn)

				# fixme: падает, если не нашли ни одного файла
				if not ope(fn):
					continue

				fsize = os.stat(fn).st_size
				if fsize == 0:
					try:
						os.unlink(fn)
					except PermissionError:
						self.videos.append((fn, fn + "\nПустой файл! Не могу удалить!", fsize, (0.0, 0)))
				else:
					fn_duration = get_duration(fn)
					new_video = (fn, get_video_title(fn), fsize, fn_duration)
					logd("adding %r", new_video)
					self.videos.append(new_video)
					if self.exit_by_self:
						# отменяем выход, если назначили его сами
						self.i_exit.set(False)
						self.exit_by_self = False
					logd("self.i_exit.get()=%r", self.i_exit.get())
					# ~ logd("self.videos=%r", self.videos)

					_duration += fn_duration[0]
					_fsize += fsize

					if announce and self.splash.working:
						# ~ logd("fn=%r", fn)
						if fn[0] == ".":
							self.splash.l_fn["text"] = fn[2:]
						perc = fn_count / fn_total * 100.0
						self.splash.pb["value"] = perc
						# ~ logd("fn_count=%r, fn_total=%r, perc=%r"
						# ~ , fn_count, fn_total, perc)

						self.splash.l_progress["text"] = "%.2f %%" % self.splash.pb["value"]

						self.splash.master.title(self.splash._title + duration_fmt((_duration,)) + "    " + sizeof_fmt(_fsize))

						self.update_splash()

					if not self.splash.working and self.first_run:
						self.master.destroy()
						EXIT(16)

		save_cache(DUR_CACHE_FP, dur_cache)

	def clear_lb_videos(self):
		self.lbVideosDurations.delete(0, tk.END)
		self.lbVideosSizes.delete(0, tk.END)
		self.lbVideosTitles.delete(0, tk.END)

	def sort_videos(self, announce=None):
		self.clear_lb_videos()

		if not self.videos:
			dp("! empty self.videos")
			return

		self.bVideoDuration["text"] = sDURATION
		self.bVideoSize["text"] = sFSIZE
		self.bVideoTitle["text"] = sTITLE
		self.bVideoFilename["text"] = sFN

		if self.sort_by == "duration_desc":
			self.videos.sort(key=lambda x: x[3][0], reverse=True)
			self.bVideoDuration["text"] = sDURATION_DESC

		elif self.sort_by == "duration_asc":
			self.videos.sort(key=lambda x: x[3][0], reverse=False)
			self.bVideoDuration["text"] = sDURATION_ASC

		elif self.sort_by == "fsize_desc":
			self.videos.sort(key=lambda x: x[2], reverse=True)
			self.bVideoSize["text"] = sFSIZE_DESC

		elif self.sort_by == "fsize_asc":
			self.videos.sort(key=lambda x: x[2], reverse=False)
			self.bVideoSize["text"] = sFSIZE_ASC

		elif self.sort_by == "fn_desc":
			self.videos.sort(key=lambda x: x[0].lower(), reverse=True)
			self.bVideoFilename["text"] = sFN_DESC

		elif self.sort_by == "fn_asc":
			self.videos.sort(key=lambda x: x[0].lower(), reverse=False)
			self.bVideoFilename["text"] = sFN_ASC

		elif self.sort_by == "title_desc":
			self.videos.sort(key=lambda x: x[1], reverse=True)
			self.bVideoTitle["text"] = sTITLE_DESC

		elif self.sort_by == "title_asc":
			self.videos.sort(key=lambda x: x[1], reverse=False)
			self.bVideoTitle["text"] = sTITLE_ASC

		else:
			loge("\n! unknown self.sort_by=%r" % self.sort_by)

		idx = 0
		max_len_fsize = 0
		max_len_duration = 0
		total_duration = 0
		total_fsize = 0
		for item in self.videos:
			fn, title, fsize, duration = item
			total_duration += duration[0]
			total_fsize += fsize
			sduration = duration_fmt(duration)
			sfsize = sizeof_fmt(fsize)
			self.lbVideosDurations.insert(tk.END, sduration)
			self.lbVideosSizes.insert(tk.END, sfsize)
			self.lbVideosTitles.insert(tk.END, " " + title.replace("\n", " / "))

			bgcolor = self._palette["SystemWindow"]
			if idx % 2 == 0:  # odd
				bgcolor = darker(bgcolor)
			else:  # even
				bgcolor = bgcolor

			self.lbVideosSizes.itemconfig(idx, bg=bgcolor)
			self.lbVideosDurations.itemconfig(idx, bg=bgcolor)
			self.lbVideosTitles.itemconfig(idx, bg=bgcolor)

			idx += 1

			if max_len_fsize < len(sfsize):
				max_len_fsize = len(sfsize)
			if max_len_duration < len(sduration):
				max_len_duration = len(sduration)

			self.update_splash()

		self.lbVideosDurations["width"] = max_len_duration
		self.lbVideosSizes["width"] = max_len_fsize + 1

		self.end_title = (
			" - Всего: " + duration_fmt((total_duration, None)) + "    " + sizeof_fmt(total_fsize) + f" - {MY_NAME}"
		)
		# ~ + (" *" if config.my_changed else "")

		if announce:
			narrator = random.choice(narrators)  # nosec
			total_duration_str = td2words(timedelta(seconds=total_duration))
			self.update_splash()
			say_with_queue(total_duration_str, narrator=narrator)

	def update_splash(self):
		if self.splash.working:
			try:
				self.splash.update()
			except tk.TclError as e:  # noqa: F841
				# ~ logd("Не успели :(", exc_info=e)
				# ~ logd("Не успели :(")
				pass

	def set_sort(self, _sort_by):
		if self.sort_by == _sort_by + "_desc":
			self.sort_by = _sort_by + "_asc"
		elif self.sort_by == _sort_by + "_asc":
			self.sort_by = _sort_by + "_desc"
		else:
			self.sort_by = _sort_by + "_desc"
		self.sort_videos()

	def set_sort_duration(self):
		self.set_sort("duration")

	def set_sort_fsize(self):
		self.set_sort("fsize")

	def set_sort_fn(self):
		self.set_sort("fn")

	def set_sort_title(self):
		self.set_sort("title")

	def pause_video(self):
		self.paused = not self.paused
		# todo: send pause to player
		if ahk and self.player_pid:
			self.win_player = Window.from_pid(  # pylint: disable=E0601
				ahk,
				pid=str(self.player_pid),
			)
			if self.win_player:
				self.win_player.send("p")

	def skip_video(self):
		# done: Переспросить перед добавлением видоса в пропущенные
		if messagebox.askyesno(_("Skipped"), _("Do you want add current video into skipped?")):
			_set = self.prop_skipped
			_set.add(self.fp_video)
			self.prop_skipped = _set
			# ~ self.stop_player()
			self.restart_player()

	def clear_skipped(self):
		# done: Переспросить перед очисткой пропущенных видосов
		if messagebox.askyesno(_("Skipped"), _("Do you want to clear skipped?")):
			self.prop_skipped = set()
			self.restart_player()

	def create_widgets(self):
		self.uf = tk.Frame(self, relief="groove", bd=2)
		self.uf.pack(side="top", fill="x", expand=False, pady=8, padx=4)
		# ~ mim = tk.PhotoImage(file = "/home/slair/share/cote-640x360.png")
		self.lClock = tk.Label(self.uf, text="<lClock>", font=("a_LCDNova", 56))
		self.lClock.pack(side="right", anchor="n", pady=4)

		self.lStatus = tk.Label(self.uf, text="", font=("Impact", 48), fg="#804000")

		self.lStatus.bind("<Configure>", lambda e: self.lStatus.config(wraplength=self.lStatus.winfo_width()))

		self.lStatus.pack(side="left", fill="both", expand=True, padx=4, pady=8)

		self.mf = tk.Frame(self)
		self.mf.pack(side="top", fill="x", expand=False)

		self.f_video = tk.Frame(self.mf)  # фрейм для кнопок к текущему видео
		self.f_video.pack(side="top", fill="x", expand=False, pady=0, padx=4)

		self.b_pause = tk.Button(self.f_video, text=" Пауза ", command=self.pause_video, highlightthickness=0)
		self.b_pause.pack(side="left", fill="y", expand=False, pady=4, padx=4)

		self.b_skip = tk.Button(self.f_video, text=" Пропустить ", command=self.skip_video, highlightthickness=0)
		self.b_skip.pack(side="left", fill="y", expand=False, pady=4, padx=4)

		self.i_fullscreen = tk.IntVar(value=int(config["global"].get("fullscreen", "1")))

		self.cb_fullscreen = tk.Checkbutton(
			self.f_video,
			text=_("Fullscreen"),
			variable=self.i_fullscreen,
			onvalue=1,
			offvalue=0,
			bd=1,
			relief="raised",
			highlightthickness=0,
			command=self.cb_fullscreen_changed,
		)
		self.cb_fullscreen.pack(side="left", fill="y", padx=4, pady=4, ipady=4, ipadx=4)

		self.sv_player_display = tk.StringVar(value=self.display_names[int(config["global"].get("fs-screen", "0"))])

		# done: Выбор монитора для фулскрина
		self.cb_display = ttk.Combobox(
			self.f_video, state="readonly", textvariable=self.sv_player_display, values=self.display_names
		)
		self.cb_display.pack(side="left", fill="y", pady=4, padx=4)
		self.cb_display.bind("<<ComboboxSelected>>", self.display_selected)

		self.i_bring_to_front = tk.IntVar(value=int(config["global"].get("bring_to_front", "1")))

		self.cb_bring_to_front = tk.Checkbutton(
			self.f_video,
			text=_("Bring to front after playing"),
			highlightthickness=0,
			variable=self.i_bring_to_front,
			onvalue=1,
			offvalue=0,
			bd=1,
			relief="raised",
			command=self.cb_bring_to_front_changed,
		)
		self.cb_bring_to_front.pack(side="left", fill="y", pady=4, padx=4, ipady=4, ipadx=4)

		self.i_exit = tk.IntVar(value=int(config["global"].get("exit_after_play", "0")))

		self.cb_exit = tk.Checkbutton(
			self.f_video,
			text=_("Exit"),
			highlightthickness=0,
			variable=self.i_exit,
			onvalue=1,
			offvalue=0,
			bd=1,
			relief="raised",
			command=self.cb_exit_changed,
		)
		self.cb_exit.pack(side="left", fill="y", pady=4, padx=4, ipady=4, ipadx=4)

		self.i_delseen = tk.IntVar(value=int(config["global"].get("delete_seen_files", "0")))

		self.cb_delseen = tk.Checkbutton(
			self.f_video,
			text=_("Delete seen"),
			highlightthickness=0,
			variable=self.i_delseen,
			onvalue=1,
			offvalue=0,
			bd=1,
			relief="raised",
			command=self.cb_delseen_changed,
		)
		self.cb_delseen.pack(side="left", fill="y", pady=4, padx=4, ipady=4, ipadx=4)

		self.tpl_clear_skipped = " Очистить %d пропущенных "
		self.b_clear_skipped = tk.Button(
			self.f_video,
			text=self.tpl_clear_skipped % len(self.prop_skipped),
			highlightthickness=0,
			command=self.clear_skipped,
		)
		self.b_clear_skipped.pack(side="right", fill="y", expand=False, pady=4, padx=4)

		self.lVideoTitle = tk.Label(self.mf, text="", relief="groove", bd=2, font=("Impact", 48), wraplength=0, fg="#000080")

		self.lVideoTitle.bind("<Configure>", lambda e: self.lVideoTitle.config(wraplength=self.lVideoTitle.winfo_width()))

		self.lVideoTitle.pack(side="top", fill="x", expand=True, ipadx=8, ipady=8, pady=4, padx=4)

		self.lf = tk.Frame(self, bg=get_random_color())
		self.lf.pack(side="top", fill="both", expand=True)

		# ~ self.tFont = ("Liberation Sans Narrow", 24)
		self.tFont = ("Ubuntu Condensed", 24)

		self.df = tk.Frame(self.lf, bg=get_random_color())
		self.df.pack(side="left", fill="y", expand=False)

		self.bVideoDuration = tk.Button(self.df, text=sDURATION, highlightthickness=0, command=self.set_sort_duration)
		self.bVideoDuration.pack(side="top", fill="x", expand=False)

		self.lbVideosDurations = tk.Listbox(
			self.df,
			activestyle="none",
			highlightthickness=0,
			justify="center",
			font=self.tFont,
			bd=0,
			bg=self._palette["SystemWindow"],
		)
		self.lbVideosDurations.pack(side="top", fill="both", expand=True, pady=0)

		self.sf = tk.Frame(self.lf, bg=get_random_color())
		self.sf.pack(side="left", fill="both", expand=False)

		self.bVideoSize = tk.Button(self.sf, text=sFSIZE, highlightthickness=0, command=self.set_sort_fsize)
		self.bVideoSize.pack(side="top", fill="x", expand=False)

		self.lbVideosSizes = tk.Listbox(
			self.sf,
			activestyle="none",
			justify="center",
			font=self.tFont,
			bd=0,
			highlightthickness=1,
			highlightbackground="darkgray",
			bg=self._palette["SystemWindow"],
		)
		self.lbVideosSizes.pack(side="top", fill="y", expand=True, pady=0)

		self.tf = tk.Frame(self.lf, bg=get_random_color())
		self.tf.pack(side="left", fill="both", expand=True)

		self.fTitleButtons = tk.Frame(self.tf, bg=get_random_color())
		self.fTitleButtons.pack(side="top", fill="x", expand=False)

		self.bVideoTitle = tk.Button(self.fTitleButtons, text=sTITLE, highlightthickness=0, command=self.set_sort_title)
		self.bVideoTitle.pack(side="left", fill="x", expand=True)

		self.bVideoFilename = tk.Button(self.fTitleButtons, text=sFN, highlightthickness=0, command=self.set_sort_fn)
		self.bVideoFilename.pack(side="left", fill="x", expand=False)

		self.lbVideosTitles = tk.Listbox(
			self.tf,
			activestyle="none",
			justify="left",
			font=self.tFont,
			bd=0,
			highlightthickness=0,
			bg=self._palette["SystemWindow"],
		)
		self.lbVideosTitles.pack(side="top", fill="both", expand=True, pady=0)

		# ~ for w in all_children(self):
		# ~ w.bind("<KeyPress>", self.on_keypress)
		# ~ w.bind("<KeyRelease>", self.on_keyup)

	def stop_player(self):
		self.my_state = STOPPED
		self.my_state_start = tpc()
		if WIN32:
			self.send_key_to_player(chr(27))
		elif LINUX:
			os.system("wmctrl -v -x -c gl || wmctrl -v -x  -c xv || wmctrl -v -x  -c mpv || killall mpv")  # nosec
		start_exit = tpc()
		# ~ while self.player_pid and psutil.pid_exists(self.player_pid):
		while self.player_pid and get_pids_by_fn(self.fp_video):
			exit_duration = tpc() - start_exit
			logd("Waiting %r for the %r (%r) to die", exit_duration, self.player_pid, PLAYER_BINARY)
			time.sleep(0.1)
			if exit_duration > MAX_TIME_TO_DIE:
				logd("Killing %r (%r)", self.player_pid, PLAYER_BINARY)
				os.kill(self.player_pid)
				start_exit = tpc()

	def restart_player(self):
		self.stop_player()
		self.my_state = VIDEO_RENAMED
		self.my_state_start = tpc()

	def cb_fullscreen_changed(self):
		value = self.i_fullscreen.get()
		config_changed = change_config("global", "fullscreen", str(value))
		if config_changed:
			# ~ self.restart_player()
			if value:
				self.send_key_to_player("F")
			else:
				self.send_key_to_player("G")

	def cb_bring_to_front_changed(self):
		change_config("global", "bring_to_front", str(self.i_bring_to_front.get()))

	def cb_exit_changed(self):
		# ~ change_config("global", "exit_after_play"
		# ~ , str(self.i_exit.get()))
		pass

	def cb_delseen_changed(self):
		# ~ change_config("global", "delete_seen_files"
		# ~ , str(self.i_delseen.get()))
		pass

	def display_selected(self, event):  # noqa
		selection = self.cb_display.get()
		config_changed = change_config("global", "fs-screen", self.display_names.index(selection))
		if config_changed:
			self.restart_player()

	@property
	def prop_skipped(self):
		return self.skipped

	@prop_skipped.setter
	def prop_skipped(self, val):
		self.skipped = val
		# ~ logd("self.skipped= %r", self.skipped)

		change_config("global", "skipped", FNSEP.join(sorted(self.skipped)))

		self.b_clear_skipped["text"] = self.tpl_clear_skipped % len(self.skipped)

		if self.skipped:
			self.b_clear_skipped["state"] = "normal"
		else:
			self.b_clear_skipped["state"] = "disabled"


def main():
	# done: Загрузка настроек
	load_config()

	root = tk.Tk()
	# ~ root.overrideredirect(1)

	# ~ sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
	# ~ logd("screen=%rx%r", sw, sh)

	geometry = config["global"].get("geometry", None)
	if geometry:
		root.geometry(geometry)
	else:
		root.geometry("1024x512+" + str(1366 - 1024 - 7) + "+" + str(720 - 512 - 31))

	SCRIPTPATH = os.path.dirname(os.path.realpath(__file__))
	icon = tk.PhotoImage(file=os.path.join(SCRIPTPATH, "icon.png"))
	root.iconphoto(True, icon)

	# ~ logd("sys.argv=%r", sys.argv)
	if len(sys.argv) > 1 and sys.argv[1][0] == "-":
		app = Application(root, sys.argv[1][1:])
	else:
		app = Application(root)
	app.mainloop()


if __name__ == "__main__":
	if already_running(TS_PORT):
		loge("ALREADY_RUNNING TS_PORT=%r", TS_PORT)
		EXIT()

	if ope(DUR_CACHE_FP):
		dur_cache = load_cache(DUR_CACHE_FP)

	if len(sys.argv) > 1:
		folder = sys.argv[1]
		if folder[0] != "-":
			os.chdir(folder)
			# fixme: надо ли проверить наличие dont_delete_flag

	logi("Starting %r in %r", " ".join(sys.argv), os.getcwd())

	if DONT_DELETE:
		say("Не буду удалять файлы из этого каталога")

	main()
	saymod.TS_ACTIVE = False
	EXIT()
