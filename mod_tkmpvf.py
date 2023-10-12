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
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta
import threading

import cv2
import psutil

#~ # pylint: disable=E0611
from transliterate import translit	 # , get_available_language_codes
#~ get_available_language_codes()	 # без этого заменяются языки
import translit_pikabu_lp			 # noqa добавляем свой язык
from num2t4ru import num2text		 # , num2text_VP
#~ # pylint: disable=

WIN32 = sys.platform == "win32"
LINUX = sys.platform == "linux"
TMPDIR = tempfile.gettempdir()

# todo: убрать ahk, трэй бесится и слишком накладно ради одного
# send_key_to_player
ahk = None
if WIN32:
	from ahk import AHK
	from ahk.window import Window
	ahk = AHK()

#~ video_folder = r"C:\slair\to-delete\tg all"
video_folder = r"."

PLAYER_BINARY = "mpv.exe"
TPL_PLAY_CMD = " ".join((
	PLAYER_BINARY,
	"-fs",
	"--fs-screen=1",
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


#~ def my_tk_excepthook(excType, excValue, ltraceback, *args):
def my_tk_excepthook(*args):
	logc("args= %r", args, exc_info=args)

	pid_fp = os.path.join(TMPDIR, os.path.basename(__file__) + ".pid")
	if os.path.exists(pid_fp):
		if pid_fd:
			pid_fd.close()
		try:
			os.unlink(pid_fp)
			logi("Deleting %r", pid_fp)
		except PermissionError as e:
			loge("Deleting %r", pid_fp, exc_info=e)

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


def get_duration(filename):
	video = cv2.VideoCapture(filename)

	duration = video.get(cv2.CAP_PROP_POS_MSEC)
	frame_count = video.get(cv2.CAP_PROP_FRAME_COUNT)
	if duration <= 0:
		#~ print("! duration = %r" % duration)
		fps = video.get(cv2.CAP_PROP_FPS)
		duration = frame_count / fps
		#~ print("! duration(frame_count / fps) = %r / %r = %r" % (
			#~ frame_count, fps, duration))

	if duration <= 0:
		print("! Bad duration=%r video=%r" % (duration, filename))
		duration = 0

	return duration, frame_count

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

	if s.count(PARTSEP) == 2:
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

	res = str(timedelta(seconds=dur_sec))

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

	def __init__(self, master=None):
		super().__init__(master)
		self.master = master
		self.pack(side="top", fill=tk.BOTH, expand=True)
		self._title = "Загрузка...    "
		self.master.title(self._title)

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


def EXIT(rc=0):
	save_config()
	# wait for all threads to complete
	threads = None
	while not threads or len(threads) > 1:
		threads = threading.enumerate()
		#~ logd("%r", " ".join(t.name for t in threads))
	logi("Exiting rc=%r\n\n", rc)
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

	def __init__(self, master=None, sort_by="fsize_desc"):
		super().__init__(master)
		self.sort_by = sort_by
		self.master = master
		self._base_title = "tkmpvf - %s" % os.getcwd()
		self.master.title(self._base_title)
		self.pack(side="top", fill="both", expand=True)
		self.create_widgets()
		self.master.bind("<KeyPress>", self.on_keypress)
		self.bind("<KeyPress>", self.on_keypress)
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

		self.on_every_second()
		#~ self.master.state('zoomed')
		#~ self.master.state("iconic")

	def start_video(self):
		self.fp_video = None
		while not self.fp_video and self.videos:
			self.fp_video, title, fsize, duration = self.videos.pop(0)
			if self.fp_video in self.prop_skipped:
				self.fp_video = None

		p = do_command_bg(TPL_PLAY_CMD % self.fp_video)
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

	def bring_to_front(self):
		self.master.state("normal")
		self.master.focus_force()
		self.b_skip.focus()

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
		now = datetime.now()
		self.lClock["text"] = now.strftime("%H:%M:%S")

		self.change_label_height(self.lVideoTitle
			, min_height=100, max_height=200)

		if self.player_pid:
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
					self.master.after(1000, self.on_every_second)
					return

				else:
					self.my_state = VIDEO_RENAMED
					self.my_state_start = tpc()

			if self._points_added <= TIME_TO_RENAME:
				self.lVideoTitle["text"] += "."
				self._points_added += 1

		elif self.my_state == VIDEO_RENAMED:
			if tpc() - self.my_state_start > TIME_TO_START:
				self.get_videos(self.first_run)

				if self.videos:
					self.my_state = PLAYING
					self.my_state_start = tpc()
					if self.first_run:
						self.sort_videos(self.first_run)
						self.first_run = None
						self.splash.master.destroy()
						self.master.deiconify()
					self.start_video()
				else:
					self.my_state = STOPPED
					self.my_state_start = tpc()
					self.clear_lb_videos()

		elif self.my_state == STOPPED:
			snd_play_async(opj(ENV_HOME, "share", "sounds", "click-6.wav"))
			state_duration = tpc() - self.my_state_start

			self.lVideoTitle["text"] = "выход через %.1f" \
				% (TIME_TO_EXIT - state_duration)

			self.lStatus["text"] = "Нет video"
			if state_duration > TIME_TO_EXIT:
				snd_play_async(opj(ENV_HOME, "share", "sounds", "drum.wav")
					, ep=True)
				self.master.destroy()

		self.master.after(1000, self.on_every_second)

	def send_key_to_player(self, key):
		if ahk and self.player_pid:
			self.win_player = Window.from_pid(ahk
				, pid=str(self.player_pid))
			if self.win_player:
				self.win_player.send(key)
				return True
		return False

	def on_keypress(self, e):
		if e.keysym == "Escape":
			self.send_key_to_player(chr(27))
			self.master.destroy()

		else:
			print(e)

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

		if announce:
			count_videos = len(_)
			if count_videos > 0:
				self.splash = Splash(tk.Tk())
				suffix = random.choice(ann_suffixes)
				numsuf = num2text(count_videos, (suffix, "m"))  # .split()
				narrator = random.choice(narrators)
				self.splash.l_fn["text"] = ""
				self.splash.l_progress["text"] = ""
				self.splash.update()
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

					if announce:
						self.splash.l_fn["text"] = fn[2:]
						self.splash.pb["value"] = fn_count / fn_total * 100.0

						self.splash.l_progress["text"] = "%.2f %%" \
							% self.splash.pb["value"]

						self.splash.master.title(
							self.splash._title + duration_fmt((_duration,))
							+ "    " + sizeof_fmt(_fsize))

						self.splash.update()

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

		self.lbVideosDurations["width"] = max_len_duration
		self.lbVideosSizes["width"] = max_len_fsize + 1

		self.master.title(self._base_title + " - Всего: "
			+ duration_fmt((total_duration, None))
			+ "    " + sizeof_fmt(total_fsize))

		if announce:
			narrator = random.choice(narrators)
			total_duration_str = td2words(timedelta(seconds=total_duration))
			say(total_duration_str, narrator=narrator)

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
				# todo: change text on b_pause

	def skip_video(self):
		_set = self.prop_skipped
		_set.add(self.fp_video)
		self.prop_skipped = _set

		self.send_key_to_player(chr(27))

	def clear_skipped(self):
		self.prop_skipped = set()

	def create_widgets(self):
		# todo: Выбор монитора для фулскрина
		# todo: Сохранение настроек
		# todo: Загрузка настроек

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

		for w in all_children(self):
			w.bind("<KeyPress>", self.on_keypress)

	@property
	def prop_skipped(self):
		return self.skipped

	@prop_skipped.setter
	def prop_skipped(self, val):
		self.skipped = val
		#~ logd("self.skipped= %r", self.skipped)

		config["global"]["skipped"] = FNSEP.join(self.skipped)
		config.my_changed = True

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
				os.unlink(pid_fp)
				pid_fd = None
		else:
			try:
				os.unlink(pid_fp)		# здесь должно падать
			except PermissionError:
				say_async("Уже запущено!"
					, narrator=random.choice(narrators))
				EXIT(32)

	else:
		if not end:
			pid = os.getpid()
			pid_fd = open(pid_fp, "w")
			pid_fd.write("%d" % pid)	 # оставляем открытым, чтобы не потёрли


def main():
	#~ for var, value in globals().items():
		#~ logd("%16s = %s", var, value)

	check_for_running()

	load_config()

	root = tk.Tk()
	#~ print(root["bg"])
	#~ sys.exit(0)

	root.geometry("1024x512+" + str(1366 - 1024 - 7)
		+ "+" + str(720 - 512 - 31))

	scriptpath = os.path.dirname(os.path.realpath(__file__))
	icon = tk.PhotoImage(file=os.path.join(scriptpath, "icon.png"))
	root.iconphoto(True, icon)

	if len(sys.argv) > 1:
		app = Application(root, sys.argv[1][1:])
	else:
		app = Application(root)
	app.mainloop()

	#~ logi("Finished")

	check_for_running(True)


if __name__ == '__main__':
	#~ os.chdir(r"C:\slair\to-delete\tg all")
	logi("Starting")
	main()
	EXIT()
