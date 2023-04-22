#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import random
import glob
import tempfile
import re
import tkinter as tk
from datetime import datetime, timedelta

from transliterate import translit  # , get_available_language_codes
#~ get_available_language_codes()	# без этого заменяются языки
#~ import translit_pikabu_lp		# добавляем свой язык

from num2t4ru import num2text		# , num2text_VP
from saymod import say_async		# , get_narrators

import cv2

player_binary = "mpv.exe"
play_cmd_tpl = " ".join((
	player_binary,
	"-fs",
	"--fs-screen=0",
	"--softvol-max=500",
	"--brightness=10",
	"--",
	'"%s"',
))

_DEBUG = True

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

PARTSEP = "·"

opj = os.path.join

WIN32 = sys.platform == "win32"
LINUX = sys.platform == "linux"
tmpdir = tempfile.gettempdir()

my_file_name = os.path.abspath(__file__)
if os.path.islink(my_file_name):
	my_file_name = os.readlink(my_file_name)
my_folder = os.path.dirname(my_file_name)
my_name = os.path.splitext(os.path.basename(my_file_name))[0]

#~ log|


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
	if duration == 0:
		fps = video.get(cv2.CAP_PROP_FPS)
		duration = frame_count / fps

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
	return res[0].upper() + res[1:]


def get_video_title(s):
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

	#~ title = untranslit(title)
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


def get_videos(folder=".", announce=None):
	res = []
	_ = glob.glob(opj(folder, "*.mp4"))
	_ += glob.glob(opj(folder, "*.mkv"))
	_ += glob.glob(opj(folder, "*.avi"))
	_ += glob.glob(opj(folder, "*.webm"))
	_ += glob.glob(opj(folder, "*.m4v"))
	_ += glob.glob(opj(folder, "*.mov"))
	_ += glob.glob(opj(folder, "*.dat"))

	if announce:
		count_videos = len(_)
		prefix = random.choice(ann_prefixes)
		suffix = random.choice(ann_suffixes)
		numsuf = num2text(count_videos, (suffix, "m")).split()
		narrator = random.choice(narrators)
		say_async((prefix, " ".join(numsuf[:-1]), numsuf[-1])
			, narrator=narrator)

	for fn in _:
		fsize = os.stat(fn).st_size
		if fsize == 0:
			try:
				os.unlink(fn)
			except PermissionError:
				res.append((fn + " Пустой файл! Не могу удалить!"
					, fsize))
		else:
			res.append((fn, get_video_title(fn), fsize, get_duration(fn)))
	return res


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


class Application(tk.Frame):
	video_folder = r"C:\slair\to-delete\videos"
	_palette = {
		"SystemWindow" : "#dac9bf",
	}
	sort_by = "fn_asc"

	def __init__(self, master=None):
		super().__init__(master)
		self.master = master
		self.master.title("tkmpvf - %s" % self.video_folder)
		self.pack(side="top", fill="both", expand=True)
		self.create_widgets()
		self.on_every_second()
		self.bind("<KeyPress>", self.on_keypress)
		self.focus()
		self.master.state('zoomed')
		self.master.after(1000, self.on_every_second)
		self.get_videos(True)
		self.sort_videos()
		self.start_video()

	def start_video(self):
		fn, title, fsize, duration = self.videos.pop(0)
		#~ do_command(play_cmd_tpl % fn)
		self.lVideoTitle["text"] = title
		count_videos = len(self.videos)
		self.lStatus["text"] = "Осталось %s %s" % (count_videos, "video")
		self.sort_videos()

	def on_every_second(self):
		now = datetime.now()
		self.lClock["text"] = now.strftime("%H:%M:%S")
		self.master.after(1000, self.on_every_second)

	def on_keypress(self, e):
		#~ print(e)
		if e.keysym == "Escape":
			self.master.destroy()

	def get_videos(self, announce=None):
		self.videos = get_videos(self.video_folder, announce)

	def sort_videos(self):
		if not self.videos:
			print("! empty self.videos")
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
			self.videos.sort(key=lambda x: x[0], reverse=True)
			self.bVideoFilename["text"] = sFN_DESC

		elif self.sort_by == "fn_asc":
			self.videos.sort(key=lambda x: x[0], reverse=False)
			self.bVideoFilename["text"] = sFN_ASC

		elif self.sort_by == "title_desc":
			self.videos.sort(key=lambda x: x[1], reverse=True)
			self.bVideoTitle["text"] = sTITLE_DESC

		elif self.sort_by == "title_asc":
			self.videos.sort(key=lambda x: x[1], reverse=False)
			self.bVideoTitle["text"] = sTITLE_ASC

		else:
			print("! unknown self.sort_by=%r" % self.sort_by)

		self.lbVideosDurations.delete(0, tk.END)
		self.lbVideosSizes.delete(0, tk.END)
		self.lbVideosTitles.delete(0, tk.END)
		idx = 0
		max_len_fsize = 0
		max_len_duration = 0
		for item in self.videos:
			fn, title, fsize, duration = item
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

	def create_widgets(self):
		self.uf = tk.Frame(self)
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

		self.lVideoTitle = tk.Label(self.mf, text="<lVideoTitle>\n2nd line"
			, relief="groove", bd=2, font=("Impact", 48)
			, wraplength=0, fg="#000080")

		self.lVideoTitle.bind('<Configure>'
			, lambda e: self.lVideoTitle.config(
				wraplength=self.lVideoTitle.winfo_width()))

		self.lVideoTitle.pack(side="top", fill="x", expand=True)

		self.lf = tk.Frame(self)
		self.lf.pack(side="top", fill="both", expand=True)

		self.tFont = ("Liberation Serif", 24)

		self.df = tk.Frame(self.lf, bg="#800000")
		self.df.pack(side="left", fill=None, expand=False)

		self.bVideoDuration = tk.Button(self.df, text=sDURATION
			, relief="flat", command=self.set_sort_duration)
		self.bVideoDuration.pack(side="top", fill="x", expand=False)

		self.lbVideosDurations = tk.Listbox(self.df, activestyle="none"
			#~ , listvariable=self.lvVDurations
			, justify="center", font=self.tFont, bd=0
			, bg=self._palette["SystemWindow"])
		self.lbVideosDurations.pack(side="top", fill=None, expand=True, pady=0)

		self.sf = tk.Frame(self.lf)
		self.sf.pack(side="left", fill="x", expand=False)

		self.bVideoSize = tk.Button(self.sf, text=sFSIZE, relief="flat"
			, command=self.set_sort_fsize)
		self.bVideoSize.pack(side="top", fill="x", expand=False)

		self.lbVideosSizes = tk.Listbox(self.sf, activestyle="none"
			, justify="center", font=self.tFont, bd=0
			, bg=self._palette["SystemWindow"])
		self.lbVideosSizes.pack(side="top", fill="both", expand=True)

		self.tf = tk.Frame(self.lf)
		self.tf.pack(side="left", fill="x", expand=True)

		self.fTitleButtons = tk.Frame(self.tf)
		self.fTitleButtons.pack(side="top", fill="x", expand=True)

		self.bVideoTitle = tk.Button(self.fTitleButtons, text=sTITLE
			, relief="flat"
			, command=self.set_sort_title)
		self.bVideoTitle.pack(side="left", fill="x", expand=True)

		self.bVideoFilename = tk.Button(self.fTitleButtons, text=sFN
			, relief="flat"
			, command=self.set_sort_fn)
		self.bVideoFilename.pack(side="left", fill="x", expand=False)

		self.lbVideosTitles = tk.Listbox(self.tf, activestyle="none"
			, justify="left", font=self.tFont, bd=0
			, bg=self._palette["SystemWindow"])
		self.lbVideosTitles.pack(side="top", fill="both", expand=True)

		for w in all_children(self):
			w.bind("<KeyPress>", self.on_keypress)


def main():
	#~ logi("Started")
	#~ for var, value in globals().items():
		#~ logd("%16s = %s", var, value)

	root = tk.Tk()
	root.geometry("1024x512+100+100")
	app = Application(root)
	app.mainloop()

	#~ logi("Finished")


if __name__ == '__main__':
	main()
