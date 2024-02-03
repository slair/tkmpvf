#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import random
import glob
import tempfile
import time
import re
import logging
import subprocess
import configparser
import shutil
import gettext
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
import threading

import psutil

#~ from tinytag import TinyTag
from subprocess import check_output

ope = os.path.exists
#~ # pylint:disable=E0611
from transliterate import translit	 # , get_available_language_codes
#~ get_available_language_codes()	 # без этого заменяются языки
import translit_pikabu_lp			 # noqa добавляем свой язык
from num2t4ru import num2text		 # , num2text_VP
#~ # pylint:disable=

_ = gettext.gettext

WIN32 = sys.platform == "win32"
LINUX = sys.platform == "linux"
TMPDIR = tempfile.gettempdir()

if WIN32:
	from ctypes import windll

	timeBeginPeriod = windll.winmm.timeBeginPeriod
	timeBeginPeriod(1)

	import win32api

	def enum_display_monitors():
		res = []
		for mon in win32api.EnumDisplayMonitors():
			width = mon[2][2] - mon[2][0]
			height = mon[2][3] - mon[2][1]
			if mon[2][0] < 0:
				#~ res.append("left", width, height)
				res.append("%rx%r" % (width, height))
			elif mon[2][0] >= 0:
				#~ res.append("right", width, height)
				res.append("%rx%r" % (width, height))
		return res

PLAYER = "mpv"

if WIN32:
	PLAYER += ".exe"

# todo: убрать ahk, трэй бесится, слишком дорого ради одного send_key_to_player
ahk = None
if WIN32:
	from ahk import AHK
	from ahk.window import Window
	ahk = AHK()

#~ video_folder = r"C:\slair\to-delete\tg all"
video_folder = r"."

PLAYER_BINARY = shutil.which(PLAYER)
TPL_PLAY_CMD = " ".join((
	PLAYER_BINARY,
	"%s",						# "-fs",
	"--fs-screen=%s",
	"--softvol-max=500",
	"--brightness=0",
	"--",
	'"%s"',
))

_DEBUG = True

FNSEP = "|"				# FileName SEParator in ini file
FS_CHANGE_STEP = 3		# Font Size CHANGE STEP

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
COLOR_RENAMED_BG_NORM = "SystemButtonFace"

COLOR_RENAMED_FG_FAILED = "#800000"
COLOR_RENAMED_BG_FAILED = "#ffff00"

COLOR_FG_TITLE = "#000080"
COLOR_BG_TITLE = "SystemButtonFace"

PARTSEP = "·"

opj = os.path.join
tpc = time.perf_counter
config = configparser.ConfigParser()
config["global"] = {}
config.my_changed = False
pid_fd = None

MY_FILE_NAME = os.path.abspath(__file__)
if os.path.islink(MY_FILE_NAME):
	MY_FILE_NAME = os.readlink(MY_FILE_NAME)
MY_FOLDER = os.path.dirname(MY_FILE_NAME)
MY_NAME = os.path.splitext(os.path.basename(MY_FILE_NAME))[0]


try:
	from saymod import say_async, say, snd_play_async, saymod_setup_log
	saymod_setup_log(MY_NAME)
except ModuleNotFoundError:
	def say(*args, **kwargs):
		print("! say(", *args, ")")

	def snd_play_async(*args, **kwargs):
		print("! snd_play_async(", *args, ")")

	def say_async(*args, **kwargs):
		print("! say_async(", *args, ")")


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
print("LOG_FILE_NAME = %r" % LOG_FILE_NAME)

fh = logging.FileHandler(LOG_FILE_NAME, encoding="utf-8")
formatter = logging.Formatter(FLN + BASELOGFORMAT, BASEDTFORMAT)
fh.setFormatter(formatter)
logger.addHandler(fh)

if "HOME" in os.environ:
	ENV_HOME = os.environ["HOME"]
elif "USERPROFILE" in os.environ:
	logw("No HOME environment variable, using USERPROFILE")
	ENV_HOME = os.environ["USERPROFILE"]
else:
	loge("No HOME or USERPROFILE environment variable")
	ENV_HOME = ""

if "XDG_DATA_HOME" in os.environ:
	XDG_DATA_HOME = os.environ["XDG_DATA_HOME"]
elif "APPDATA" in os.environ:
	XDG_DATA_HOME = os.environ["APPDATA"]
elif ENV_HOME:
	XDG_DATA_HOME = opj(ENV_HOME, opj(".local", "share"))

MY_XDG_DATA_HOME = opj(XDG_DATA_HOME, MY_NAME)
if not os.path.exists(MY_XDG_DATA_HOME):
	logi("Create folder %r", MY_XDG_DATA_HOME)
	os.makedirs(MY_XDG_DATA_HOME)

if "XDG_CONFIG_HOME" in os.environ:
	XDG_CONFIG_HOME = os.environ["XDG_CONFIG_HOME"]
elif "LOCALAPPDATA" in os.environ:
	XDG_CONFIG_HOME = os.environ["LOCALAPPDATA"]
elif ENV_HOME:
	XDG_CONFIG_HOME = opj(ENV_HOME, ".config")

MY_XDG_CONFIG_HOME = opj(XDG_CONFIG_HOME, MY_NAME)
if not os.path.exists(MY_XDG_CONFIG_HOME):
	logi("Create folder %r", MY_XDG_CONFIG_HOME)
	os.makedirs(MY_XDG_CONFIG_HOME)

CONFIG_FILE_PATH = opj(MY_XDG_CONFIG_HOME, MY_NAME + ".ini")

SND_FOLDER = opj(ENV_HOME, "share", "sounds")
SND_CLICK = opj(SND_FOLDER, "click-06.wav")
SND_DRUM = opj(SND_FOLDER, "drum.wav")

dur_cache = dict()  # note: кэш, чтобы не сканировать файлы каждый раз
dur_cache_changed = False
DUR_CACHE_FN = "%s-dur-cache.txt" % MY_NAME
MAX_DURATION = 7 * 24 * 60 * 60  # неделя в секундах
mi_bin = shutil.which("MediaInfo.exe")


def save_cache(fp: str, cache: dict, datasep: str = "|"):
	global dur_cache_changed
	if not dur_cache_changed:
		return

	with open(fp, "w", encoding="utf-8", newline="\n") as handle:
		logi("Dumping %d items to %r", len(cache), fp)
		#~ json.dump(cache, handle, ensure_ascii=False, indent=4)
		res = ""
		for k, v in cache.items():
			res += "%s%s%s\n" % (k, datasep, v)
		handle.write(res)
		dur_cache_changed = False


def load_cache(fp: str, datasep: str = "|") -> dict:
	global dur_cache_changed
	with open(fp, 'r', encoding="utf-8", newline="\n") as handle:
		#~ res = json.load(handle)
		res = dict()
		fc = handle.read()
		for line in fc.split("\n"):
			data = line.split(datasep)
			if data[0]:
				res[data[0]] = float(data[1])
		logi("Read %d items from %r", len(res), fp)
		dur_cache_changed = False
	return res


def get_duration(fp) -> int:
	global dur_cache, dur_cache_changed
	if ope(fp):
		fstat = os.stat(fp)
		cfp = "%s %s %s %s" % (fp, fstat.st_size, fstat.st_ctime
			, fstat.st_mtime)
		if cfp in dur_cache:
			duration = dur_cache[cfp]
		else:
			si = subprocess.STARTUPINFO()
			si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
			#si.wShowWindow = subprocess.SW_HIDE # default
			try:
				duration = int(check_output(
					f'"{mi_bin}" --Inform="Audio;%Duration%" "{fp}"'
					, shell=False, startupinfo=si))

				duration /= 1000

				if duration > MAX_DURATION:
					logw("Wrong duration=%r, fp=%r changed to %r"
						, duration, fp, 0)
					duration = 0

				dur_cache[cfp] = duration
				if not dur_cache_changed:
					dur_cache_changed = True
			except ValueError as e:
				#~ loge("fp=%r", fp, exc_info=e)
				duration = 0
				logw("Cant get fp=%r duration, changed to %r"
					, fp, 0)

		return duration, 0

	return 0, 0


DUR_CACHE_FP = opj(TMPDIR, DUR_CACHE_FN)
if ope(DUR_CACHE_FP):
	dur_cache = load_cache(DUR_CACHE_FP)


#~ def my_tk_excepthook(excType, excValue, ltraceback, *args):
def my_tk_excepthook(*args):
	logc("args= %r", args, exc_info=args)

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
		logd("Change [%r][%r] from %r to %r"
			, section, option, old_value, value)

		config[section][option] = value
		config.my_changed = True
	return config.my_changed


def dp(*args):
	if _DEBUG:
		a1 = args[0]
		if isinstance(a1, str):
			bl = ""
			if a1[0] in "!><-+":
				bl = a1[0]
				#~ na0 = a1[1:]
				#~ args = (na0, *args[1:])
		print(bl + " %.2f" % tpc(), *args)


def all_children(wid):
	_list = wid.winfo_children()

	for item in _list :
		if item.winfo_children() :
			_list.extend(item.winfo_children())

	return _list


def mod_color(color, val):
	r = int(color[1:3], 16) + val
	g = int(color[3:5], 16) + val
	b = int(color[5:7], 16) + val
	if r > 255: r = 255					# noqa
	if g > 255: g = 255					# noqa
	if b > 255: b = 255					# noqa
	return "#%x%x%x" % (r, g, b)


def lighter(color, val=16):
	return mod_color(color, val)


def darker(color, val=16):
	return mod_color(color, -val)


def sizeof_fmt(num):
	for x in ['B ', 'kB', 'MB', 'GB', 'TB']:
		if num < 1024.0:
			return "%3.1f %s" % (num, x)
		num /= 1024.0


"""def get_duration(filename):
	video = cv2.VideoCapture(filename)  # pylint:disable=E1101

	duration = video.get(cv2.CAP_PROP_POS_MSEC)  # pylint:disable=E1101
	frame_count = video.get(cv2.CAP_PROP_FRAME_COUNT)  # pylint:disable=E1101
	if duration <= 0:
		#~ print("! duration = %r" % duration)
		fps = video.get(cv2.CAP_PROP_FPS)  # pylint:disable=E1101
		duration = frame_count / fps
		#~ print("! duration(frame_count / fps) = %r / %r = %r" % (
			#~ frame_count, fps, duration))

	if duration <= 0:
		print("! Bad duration=%r video=%r" % (duration, filename))
		duration = 0

	return duration, frame_count
"""
# 1566.9/60 = 26.115


def untranslit_word(w):
	#~ r = translit(w, "ru")
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


def get_video_title(s):
	if os.sep in s:
		s = os.path.basename(s)

	#~ s = strip_above_0xffff(s)

	if "Й" in s:
		s = s.replace("Й", "Й")
	if "й" in s:
		s = s.replace("й", "й")

	ls = s.lower()
	if ls.endswith(".mp4") or ls.endswith(".avi") or ls.endswith(".mov") \
		or ls.endswith(".mkv") or ls.endswith(".m4v") or ls.endswith(".dat"):
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
		title = re.sub(r'(?<=\d)[_](?=\d)', ":", title)

	elif s.count(PARTSEP) == 2:
		dt, title, _ = s.split(PARTSEP)
		title = re.sub(r'(?<=\d)[_](?=\d)', ":", title)

	elif s.count(PARTSEP) == 1:
		dt, title = s.split(PARTSEP)
		title = title[:title.rfind(".")]
		if title.split()[-1].isdigit():
			title = title[:title.rfind(" ")]

	else:
		title = s

	if title.endswith("yapfiles ru") and title != "yapfiles ru":
		title = untranslit(title[:-11])

	#~ print(title)
	#~ print(repr(title))
	#~ print()

	if channel:
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
narrators = (
	'Aleksandr',
	'Artemiy',
	'Elena',
	'Irina',
	'Pavel'
)


def duration_fmt(duration):
	dur_sec = duration[0]

	#~ if dur_sec > 1000000000000:
		#~ sys.exit()

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
		(("секунда", "секунды", "секунд"), 1, "f")
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
		return "Сейчас!"


#~ @asnc
def do_command_bg(cmd):
	proc = subprocess.Popen(cmd, shell=False, stdin=subprocess.PIPE
		, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	return proc


class Splash(tk.Frame):
	window_width = 512
	window_height = 100
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
		self.l_fn.bind('<Configure>', lambda e: self.l_fn.config(
			wraplength=self.l_fn.winfo_width()))
		self.l_fn.pack(side="top", fill=tk.BOTH, expand=True)

		self.l_progress = tk.Label(self.master, text="<progress>")
		self.l_progress.pack(side="bottom", fill=tk.BOTH, expand=True)

		self.pb = ttk.Progressbar(self.master, orient=tk.HORIZONTAL, length=100
			, mode="determinate")
		self.pb.pack(side="bottom", fill="x", expand=False)

		xpos = (self.master.winfo_screenwidth() - self.window_width) // 2
		ypos = (self.master.winfo_screenheight() - self.window_height) // 2
		self.master.geometry("%sx%s+%s+%s" % (
			self.window_width, self.window_height, xpos, ypos))
		#~ self.pb.start()
		#~ self.update()

	def on_keypress(self, e):
		if e.keysym == "Escape":
			self.working = False
			self.master.destroy()

		else:
			print(e)


def EXIT(rc=0):
	# done: Сохранение настроек
	save_config()
	save_cache(DUR_CACHE_FP, dur_cache)
	# note: wait for all threads to complete
	threads = None
	while not threads or len(threads) > 1:
		threads = threading.enumerate()
		#~ logd("%r", " ".join(t.name for t in threads))
	logi("Exiting rc=%r\n\n\n\n\n\n\n\n", rc)
	sys.exit(rc)


class Application(tk.Frame):
	my_state = None
	player_pid = None
	video_folder = video_folder
	_palette = {
		"SystemWindow" : "#dac9bf",
	}
	sort_by = None
	videos = []
	first_run = True
	skipped = set()
	lStatus_font = ("Impact", 48)
	lVideoTitle_font = ("Impact", 48)
	need_to_exit = False

	def __init__(self, master=None, sort_by="fsize_desc"):
		super().__init__(master)
		#~ logd("sort_by=%r", sort_by)
		self.sort_by = sort_by
		self.master = master
		self._base_title = "tkmpvf - %s" % os.getcwd()
		self.master.title(self._base_title)
		self.pack(side="top", fill="both", expand=True)
		self.display_names = enum_display_monitors()

		self.create_widgets()

		self.master.bind("<KeyRelease>", self.on_keyup)
		self.master.protocol("WM_DELETE_WINDOW", self.on_close_master)
		#~ self.master.bind('<Enter>'
			#~ , lambda *args: logd("<Enter> args=%r", args))
		#~ self.master.bind('<Leave>'
			#~ , lambda *args: logd("<Leave> args=%r", args))
		self.master.focus()
		self.b_skip.focus()

		self.master.withdraw()

		self.my_state = VIDEO_RENAMED
		self.my_state_start = 1

		if "global" in config and "skipped" in config["global"]:
			skipped_items = config["global"]["skipped"].split(FNSEP)
			#~ logd("skipped_items= %r", skipped_items)
			#~ logd("any(skipped_items)= %r", any(skipped_items))
			if any(skipped_items):
				self.prop_skipped = set(skipped_items)
		else:
			self.prop_skipped = set()

		logi("len(self.prop_skipped)=%r", len(self.prop_skipped))

		logd("Starts in %r, self.sort_by=%r", os.getcwd(), self.sort_by)

		self.on_every_second()
		#~ self.master.state('zoomed')
		#~ self.master.state("iconic")

	def geometry_to_config(self):
		change_config("global", "geometry", self.master.geometry())

	def ask_for_delete(self):
		seen_files = glob.glob("*.seen")
		if seen_files:

			if int(self.i_delseen.get()) == 1 \
				or messagebox.askyesnocancel("Просмотренные файлы"
					, "Удалить просмотренные файлы?"):

				cwd = os.getcwd()
				logd("cwd=%r", cwd)
				for item in seen_files:
					logw("Deleting %r", item)
					if cwd != 'C:\\slair\\work.local\\tkmpvf':
						os.unlink(item)

	def on_close_master(self, *args, **kwargs):
		self.need_to_exit = True
		self.stop_player()
		self.geometry_to_config()
		self.ask_for_delete()
		self.master.destroy()

	def start_video(self):
		self.fp_video = None
		while not self.fp_video and self.videos:
			self.fp_video, title, fsize, duration = self.videos.pop(0)
			if self.fp_video in self.prop_skipped:
				self.fp_video = None

		p = do_command_bg(TPL_PLAY_CMD % (
			"-fs" if self.i_fullscreen.get() == 1 else ""
			, self.display_names.index(self.sv_player_display.get())
			, self.fp_video))

		self.sort_videos(self.first_run)
		self.player_pid = p.pid
		self.lVideoTitle["text"] = title
		self.lVideoTitle["fg"] = COLOR_FG_TITLE
		self.lVideoTitle["bg"] = COLOR_BG_TITLE
		count_videos = len(self.videos)
		if count_videos:
			self.lStatus["text"] = "Осталось %s %s" % (count_videos, "video")
		else:
			self.lStatus["text"] = "Последнее video"
			self.i_exit.set(True)
			self.i_delseen.set(True)

	def bring_to_front(self):
		if self.i_bring_to_front.get() == 1:
			self.master.state("normal")
			self.b_skip.focus_force()

	def change_label_height(self, label, min_height, max_height):
		label_height = label.winfo_height()	 # 326
		label_font = label["font"]			 # Impact 48
		label_font_name, label_font_size = label_font.rsplit(maxsplit=1)

		label_font_size = int(label_font_size)

		if label_height > max_height:
			label_font_size -= FS_CHANGE_STEP
			label["font"] = (label_font_name
				, label_font_size)

		elif label_height < min_height:
			label_font_size += FS_CHANGE_STEP
			label["font"] = (label_font_name
				, label_font_size)

	def on_every_second(self):
		#~ logd("self.my_state=%r, duration=%r"
			#~ , self.my_state, tpc()-self.my_state_start)

		now = datetime.now()
		self.lClock["text"] = now.strftime("%H:%M:%S")

		old_title = self.master.title()
		if old_title[-1] != "*" and config.my_changed:
			self.master.title(old_title + " *")
		elif old_title[-1] == "*" and not config.my_changed:
			self.master.title(old_title[:-2])

		self.change_label_height(self.lVideoTitle
			, min_height=100, max_height=200)

		if self.player_pid and self.my_state == PLAYING:
			self.b_pause["state"] = "normal"
			self.b_skip["state"] = "normal"
			if not psutil.pid_exists(self.player_pid):
				self.player_pid = None
				self.b_pause["state"] = "disabled"
				self.b_skip["state"] = "disabled"
				self.my_state = PLAY_FINISHED
				self.my_state_start = tpc()
				self._points_added = 0
				self.bring_to_front()

		if self.my_state == PLAY_FINISHED:
			if tpc() - self.my_state_start > (TIME_TO_RENAME + 1.0)\
				and self._points_added >= TIME_TO_RENAME:

				if self.fp_video and self.fp_video not in self.prop_skipped \
					and os.path.exists(self.fp_video):

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
						rename_status = "<не удалось переименовать>"\
							"\nтакой файл уже есть"
						color_fg_renamed = COLOR_RENAMED_FG_FAILED
						color_bg_renamed = COLOR_RENAMED_BG_FAILED

					fp_name, ext = os.path.splitext(self.fp_video)
					vtt_fp = fp_name + ".ru.vtt"
					if os.path.exists(vtt_fp):
						try:
							os.rename(vtt_fp, vtt_fp + ".seen")
						except PermissionError:
							rename_status = "<vtt не удалось переименовать>\n"\
								"нет прав"
							color_fg_renamed = COLOR_RENAMED_FG_FAILED
							color_bg_renamed = COLOR_RENAMED_BG_FAILED
						except FileExistsError:
							rename_status = "<vtt не удалось переименовать>"\
								"\nтакой файл уже есть"
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

				if int(self.i_exit.get()) == 0:
					self.get_videos(self.first_run)

				if self.videos and int(self.i_exit.get()) == 0:
					self.sort_videos(self.first_run)
					if self.first_run:
						self.first_run = None
						self.splash.working = None
						self.splash.master.destroy()
						self.master.deiconify()
					self.start_video()
					self.my_state = PLAYING
					self.my_state_start = tpc()
				else:
					self.my_state = STOPPED
					self.my_state_start = tpc()
					#~ self.clear_lb_videos()

		elif self.my_state == STOPPED:
			if not self.need_to_exit:
				snd_play_async(SND_CLICK)
				state_duration = tpc() - self.my_state_start

				self.lVideoTitle["text"] = "выход через %.1f" \
					% (TIME_TO_EXIT - state_duration)

				self.lStatus["text"] = "Нет video"
				if state_duration > TIME_TO_EXIT:
					snd_play_async(SND_DRUM, ep=True)
					#~ self.master.destroy()
					self.on_close_master()

		self.after(REPINT_MSEC, self.on_every_second)

	def send_key_to_player(self, key):
		#~ logd("ahk=%r, self.player_pid=%r", ahk, self.player_pid)
		if ahk and self.player_pid:
			ahk_pid = 'ahk_pid %s' % self.player_pid
			self.win_player = ahk.win_get(title=ahk_pid)
			#~ logd("ahk_pid=%r, self.win_player=%r", ahk_pid, self.win_player)
			#~ self.win_player = Window.from_pid(ahk
				#~ , pid=str(self.player_pid))
			if self.win_player:
				logd("Send %r to %r", key, self.win_player)
				self.win_player.send(key)
				return True
		return False

	def on_keyup(self, e):
		if e.keysym == "Escape":
			self.on_close_master()
		elif e.keysym == "F12":
			self.i_exit.set(not self.i_exit.get())
			self.i_delseen.set(not self.i_delseen.get())
			logd("self.i_exit.get()=%r", self.i_exit.get())
		else:
			logd("e=%r", e)

	def get_videos(self, announce=None):
		folder = self.video_folder
		#~ logd("os.getcwd()= %r", os.getcwd())
		#~ self.videos.clear()

		_ = glob.glob(opj(folder, "*.mp4"))
		_ += glob.glob(opj(folder, "*.mkv"))
		_ += glob.glob(opj(folder, "*.avi"))
		_ += glob.glob(opj(folder, "*.webm"))
		_ += glob.glob(opj(folder, "*.m4v"))
		_ += glob.glob(opj(folder, "*.mov"))
		_ += glob.glob(opj(folder, "*.dat"))
		_ += glob.glob(opj(folder, "*.unknown_video"))

		if announce:
			count_videos = len(_)
			if count_videos > 0:
				self.splash = Splash(tk.Tk())
				suffix = random.choice(ann_suffixes)
				numsuf = num2text(count_videos, (suffix, "m"))  # .split()
				narrator = random.choice(narrators)
				self.splash.l_fn["text"] = ""
				self.splash.l_progress["text"] = ""
				self.update_splash()
				say_async(numsuf, narrator=narrator)
			else:
				say_async("А здесь нет вид^осов"
					, narrator=random.choice(narrators))
				#~ self.bring_to_front()

		#~ dp("> checking for deleted videos")
		for i, video_struct in enumerate(self.videos):
			if video_struct[0] not in _:
				dp("! deleting", i, video_struct)
				del self.videos[i]

		#~ dp("> checking for added videos")
		fn_count = 0
		fn_total = len(_)
		_duration = 0
		_fsize = 0
		for fn in _:
			if fn in self.prop_skipped:
				continue

			# считаем без self.prop_skipped, градусник не доходит до 100%
			fn_count += 1

			if not any(e[0] == fn for e in self.videos):
				#~ dp("! adding", fn)
				fsize = os.stat(fn).st_size
				if fsize == 0:
					try:
						os.unlink(fn)
					except PermissionError:
						self.videos.append((fn, fn
							+ "\nПустой файл! Не могу удалить!"
							, fsize, (0.0, 0)))
				else:
					fn_duration = get_duration(fn)
					self.videos.append((fn, get_video_title(fn), fsize
						, fn_duration))

					_duration += fn_duration[0]
					_fsize += fsize

					if announce and self.splash.working:
						#~ logd("fn=%r", fn)
						if fn[0] == ".":
							self.splash.l_fn["text"] = fn[2:]
						perc = fn_count / fn_total * 100.0
						self.splash.pb["value"] = perc
						#~ logd("fn_count=%r, fn_total=%r, perc=%r"
							#~ , fn_count, fn_total, perc)

						self.splash.l_progress["text"] = "%.2f %%" \
							% self.splash.pb["value"]

						self.splash.master.title(
							self.splash._title + duration_fmt((_duration,))
							+ "    " + sizeof_fmt(_fsize))

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
			#~ print(">", "sort by fn_asc", id(self.videos))
			#~ for item in self.videos:print(item)
			self.bVideoFilename["text"] = sFN_ASC

		elif self.sort_by == "title_desc":
			self.videos.sort(key=lambda x: x[1], reverse=True)
			self.bVideoTitle["text"] = sTITLE_DESC

		elif self.sort_by == "title_asc":
			self.videos.sort(key=lambda x: x[1], reverse=False)
			self.bVideoTitle["text"] = sTITLE_ASC

		else:
			print("! unknown self.sort_by=%r" % self.sort_by)

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
			self.lbVideosTitles.insert(tk.END, " "
				+ title.replace("\n", " / "))

			bgcolor = self._palette["SystemWindow"]
			if idx % 2 == 0:							# odd
				bgcolor = darker(bgcolor)
			else:										# even
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

		new_title = self._base_title + " - Всего: " \
			+ duration_fmt((total_duration, None)) \
			+ "    " + sizeof_fmt(total_fsize) \
			+ (" *" if config.my_changed else "")
		#~ logd("self.master.title(%r)", new_title)
		self.master.title(new_title)

		if announce:
			narrator = random.choice(narrators)
			total_duration_str = td2words(timedelta(seconds=total_duration))
			self.update_splash()
			say(total_duration_str, narrator=narrator)

	def update_splash(self):
		if self.splash.working:
			try:
				self.splash.update()
			except tk.TclError as e:		# noqa: F841
				#~ logd("Не успели :(", exc_info=e)
				#~ logd("Не успели :(")
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
		if ahk and self.player_pid:
			self.win_player = Window.from_pid(ahk, pid=str(self.player_pid))
			if self.win_player:
				self.win_player.send("p")

	def skip_video(self):
		# done: Переспросить перед добавлением видоса в пропущенные
		if messagebox.askyesno(_("Skipped")
			, _("Do you want add current video into skipped?")):
			_set = self.prop_skipped
			_set.add(self.fp_video)
			self.prop_skipped = _set
			#~ self.stop_player()
			self.restart_player()

	def clear_skipped(self):
		# done: Переспросить перед очисткой пропущенных видосов
		if messagebox.askyesno(_("Skipped")
			, _("Do you want to clear skipped?")):
			self.prop_skipped = set()
			self.restart_player()

	def create_widgets(self):
		self.uf = tk.Frame(self, relief="groove", bd=2)
		self.uf.pack(side="top", fill="x", expand=False)

		self.lClock = tk.Label(self.uf, text="<lClock>"
			, font=("a_LCDNova", 56))
		self.lClock.pack(side="right", anchor="n")

		self.lStatus = tk.Label(self.uf, text="<lStatus><lStatus>"
			, font=("Impact", 48), fg="#804000")

		self.lStatus.bind('<Configure>'
			, lambda e: self.lStatus.config(
				wraplength=self.lStatus.winfo_width()))

		self.lStatus.pack(side="right", fill="both", expand=True)

		self.mf = tk.Frame(self)
		self.mf.pack(side="top", fill="x", expand=False)

		self.f_video = tk.Frame(self.mf)  # фрейм для кнопок к текущему видео
		self.f_video.pack(side="top", fill="x", expand=False)

		self.b_pause = tk.Button(self.f_video, text=" Пауза "
			, command=self.pause_video)
		self.b_pause.pack(side="left", fill="y", expand=False, pady=4, padx=4)

		self.b_skip = tk.Button(self.f_video, text=" Пропустить "
			, command=self.skip_video)
		self.b_skip.pack(side="left", fill="y", expand=False, pady=4, padx=4)

		self.i_fullscreen = tk.IntVar(value=int(
			config["global"].get("fullscreen", "1")))

		self.cb_fullscreen = tk.Checkbutton(self.f_video, text=_("Fullscreen")
			, variable=self.i_fullscreen, onvalue=1, offvalue=0
			, command=self.cb_fullscreen_changed)
		self.cb_fullscreen.pack(side="left", fill="y", pady=4, padx=4)

		self.sv_player_display = tk.StringVar(
			value=self.display_names[
				int(config["global"].get("fs-screen", "0"))])

		# done: Выбор монитора для фулскрина
		self.cb_display = ttk.Combobox(self.f_video, state="readonly"
			, textvariable=self.sv_player_display, values=self.display_names)
		self.cb_display.pack(side="left", fill="y", pady=4, padx=4)
		self.cb_display.bind("<<ComboboxSelected>>", self.display_selected)

		self.i_bring_to_front = tk.IntVar(value=int(
			config["global"].get("bring_to_front", "1")))

		self.cb_bring_to_front = tk.Checkbutton(self.f_video
			, text=_("Bring to front after playing")
			, variable=self.i_bring_to_front, onvalue=1, offvalue=0
			, command=self.cb_bring_to_front_changed)
		self.cb_bring_to_front.pack(side="left", fill="y", pady=4, padx=4)

		self.i_exit = tk.IntVar(value=int(
			config["global"].get("exit_after_play", "0")))

		self.cb_exit = tk.Checkbutton(self.f_video
			, text=_("Exit")
			, variable=self.i_exit, onvalue=1, offvalue=0
			, command=self.cb_exit_changed)
		self.cb_exit.pack(side="left", fill="y", pady=4, padx=4)

		self.i_delseen = tk.IntVar(value=int(
			config["global"].get("delete_seen_files", "0")))

		self.cb_delseen = tk.Checkbutton(self.f_video
			, text=_("Delete seen")
			, variable=self.i_delseen, onvalue=1, offvalue=0
			, command=self.cb_delseen_changed)
		self.cb_delseen.pack(side="left", fill="y", pady=4, padx=4)

		self.tpl_clear_skipped = " Очистить %d пропущенных "
		self.b_clear_skipped = tk.Button(self.f_video
			, text=self.tpl_clear_skipped % len(self.prop_skipped)
			, command=self.clear_skipped)
		self.b_clear_skipped.pack(side="right", fill="y", expand=False
			, pady=4, padx=4)

		self.lVideoTitle = tk.Label(self.mf, text="<lVideoTitle>\n2nd line"
			, relief="groove", bd=2, font=("Impact", 48)
			, wraplength=0, fg="#000080")

		self.lVideoTitle.bind('<Configure>'
			, lambda e: self.lVideoTitle.config(
				wraplength=self.lVideoTitle.winfo_width()))

		self.lVideoTitle.pack(side="top", fill="x", expand=True)

		self.lf = tk.Frame(self)
		self.lf.pack(side="top", fill="both", expand=True)

		self.tFont = ("Liberation Sans Narrow", 24)

		self.df = tk.Frame(self.lf, bg="#800000")
		self.df.pack(side="left", fill=None, expand=False)

		self.bVideoDuration = tk.Button(self.df, text=sDURATION
			#~ , relief="flat"
			, command=self.set_sort_duration)
		self.bVideoDuration.pack(side="top", fill="x", expand=False)

		self.lbVideosDurations = tk.Listbox(self.df, activestyle="none"
			#~ , listvariable=self.lvVDurations
			, justify="center", font=self.tFont, bd=0
			, bg=self._palette["SystemWindow"])
		self.lbVideosDurations.pack(side="top", fill="both", expand=True
			, pady=0)

		self.sf = tk.Frame(self.lf)
		self.sf.pack(side="left", fill="x", expand=False)

		self.bVideoSize = tk.Button(self.sf, text=sFSIZE
			#~ , relief="flat"
			, command=self.set_sort_fsize)
		self.bVideoSize.pack(side="top", fill="x", expand=False)

		self.lbVideosSizes = tk.Listbox(self.sf, activestyle="none"
			, justify="center", font=self.tFont, bd=0
			, bg=self._palette["SystemWindow"])
		self.lbVideosSizes.pack(side="top", fill="both", expand=True, pady=0)

		self.tf = tk.Frame(self.lf)
		self.tf.pack(side="left", fill="x", expand=True)

		self.fTitleButtons = tk.Frame(self.tf)
		self.fTitleButtons.pack(side="top", fill="x", expand=True)

		self.bVideoTitle = tk.Button(self.fTitleButtons, text=sTITLE
			#~ , relief="flat"  # , cursor="target"
			, command=self.set_sort_title)
		self.bVideoTitle.pack(side="left", fill="x", expand=True)

		self.bVideoFilename = tk.Button(self.fTitleButtons, text=sFN
			#~ , relief="flat"
			, command=self.set_sort_fn)
		self.bVideoFilename.pack(side="left", fill="x", expand=False)

		self.lbVideosTitles = tk.Listbox(self.tf, activestyle="none"
			, justify="left", font=self.tFont, bd=0
			, bg=self._palette["SystemWindow"])
		self.lbVideosTitles.pack(side="top", fill="both", expand=True, pady=0)

		#~ for w in all_children(self):
			#~ w.bind("<KeyPress>", self.on_keypress)
			#~ w.bind("<KeyRelease>", self.on_keyup)

	def stop_player(self):
		self.my_state = STOPPED
		self.my_state_start = tpc()
		self.send_key_to_player(chr(27))
		start_exit = tpc()
		while self.player_pid and psutil.pid_exists(self.player_pid):
			exit_duration = tpc() - start_exit
			logd("Waiting %r for the %r (%r) to die", exit_duration
				, self.player_pid, PLAYER_BINARY)
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
		config_changed = change_config("global", "fullscreen"
			, str(value))
		if config_changed:
			#~ self.restart_player()
			if value:
				self.send_key_to_player("F")
			else:
				self.send_key_to_player("G")

	def cb_bring_to_front_changed(self):
		change_config("global", "bring_to_front"
			, str(self.i_bring_to_front.get()))

	def cb_exit_changed(self):
		#~ change_config("global", "exit_after_play"
			#~ , str(self.i_exit.get()))
		pass

	def cb_delseen_changed(self):
		#~ change_config("global", "delete_seen_files"
			#~ , str(self.i_delseen.get()))
		pass

	def display_selected(self, event):
		selection = self.cb_display.get()
		config_changed = change_config("global", "fs-screen"
			, self.display_names.index(selection))
		if config_changed:
			self.restart_player()

	@property
	def prop_skipped(self):
		return self.skipped

	@prop_skipped.setter
	def prop_skipped(self, val):
		self.skipped = val
		#~ logd("self.skipped= %r", self.skipped)

		change_config("global", "skipped", FNSEP.join(sorted(self.skipped)))

		self.b_clear_skipped["text"] \
			= self.tpl_clear_skipped % len(self.skipped)

		if self.skipped:
			self.b_clear_skipped["state"] = "normal"
		else:
			self.b_clear_skipped["state"] = "disabled"


def check_for_running(end=False):
	global pid_fd
	pid_fp = os.path.join(TMPDIR, os.path.basename(__file__) + ".pid")

	if os.path.exists(pid_fp):
		if end:
			if pid_fd:
				pid_fd.close()
				try:
					os.unlink(pid_fp)
					logd("Deleted %r", pid_fp)
				except PermissionError as e:
					logw("Deleting %r failed. %r", pid_fp, e)
				pid_fd = None
		else:
			try:
				os.unlink(pid_fp)		# здесь должно падать
				logd("Deleted %r", pid_fp)
			except PermissionError as e:
				logw("Deleting %r failed. %r", pid_fp, e)
				say_async("Уже запущено!"
					, narrator=random.choice(narrators))
				EXIT(32)

	else:
		if not end:
			pid = os.getpid()
			logd("Creating %r", pid_fp)
			pid_fd = open(pid_fp, "w")
			pid_fd.write("%d" % pid)	 # оставляем открытым, чтобы не потёрли


def main():
	# done: Загрузка настроек
	load_config()

	root = tk.Tk()

	#~ sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
	#~ logd("screen=%rx%r", sw, sh)

	geometry = config["global"].get("geometry", None)
	if geometry:
		root.geometry(geometry)
	else:
		root.geometry("1024x512+" + str(1366 - 1024 - 7)
			+ "+" + str(720 - 512 - 31))

	SCRIPTPATH = os.path.dirname(os.path.realpath(__file__))
	icon = tk.PhotoImage(file=os.path.join(SCRIPTPATH, "icon.png"))
	root.iconphoto(True, icon)

	#~ logd("sys.argv=%r", sys.argv)
	if len(sys.argv) > 1 and sys.argv[1][0] == "-":
		app = Application(root, sys.argv[1][1:])
	else:
		app = Application(root)
	app.mainloop()


if __name__ == '__main__':
	if len(sys.argv) > 1:
		folder = sys.argv[1]
		if folder[0] != "-":
			os.chdir(folder)

	logi("Starting %r in %r", " ".join(sys.argv), os.getcwd())
	check_for_running()
	main()
	check_for_running(True)
	EXIT()
       