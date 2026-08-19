#!/usr/bin/env python3
"""
Лек монитор за CPU и Memory за Linux Mint / Ubuntu
Показва натоварването в реално време с графики.
RAM в гигабайти + отделни нишки за CPU.
Работи само със стандартен Python + tkinter.
"""

import tkinter as tk
from collections import deque


class CpuMemMonitor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CPU & Memory")
        self.geometry("340x250")
        self.minsize(200, 160)
        self.configure(bg="#1a1a1a")

        # Always on top по подразбиране
        self.attributes("-topmost", True)
        self.topmost = True

        # История (последните ~60 секунди)
        self.history_len = 60

        # Брой нишки
        self.num_threads = self._get_num_threads()

        # История за всяка нишка + обща за памет
        self.cpu_histories = [
            deque([0.0] * self.history_len, maxlen=self.history_len)
            for _ in range(self.num_threads)
        ]
        self.mem_history = deque([0.0] * self.history_len, maxlen=self.history_len)

        # Предишни стойности за всяка нишка
        self.prev_idles = [0] * self.num_threads
        self.prev_totals = [0] * self.num_threads
        self._init_cpu()

        # Обща памет (в KB) – четем веднъж
        self.mem_total_kb = self._get_mem_total()

        # Цветове
        self.bg = "#1a1a1a"
        self.fg = "#e0e0e0"
        self.cpu_colors = ["#00e5ff", "#ff6d00", "#f50057", "#ffea00"]  # циан, оранжев, розов, жълт
        self.mem_color = "#7fff00"   # ярко лайм / chartreuse зелено
        self.grid_color = "#333333"
        self.label_bg = "#252525"

        # === Горен панел ===
        self.top_frame = tk.Frame(self, bg=self.bg)
        self.top_frame.pack(fill=tk.X, padx=6, pady=(6, 2))

        self.cpu_label = tk.Label(
            self.top_frame, text="CPU: --%",
            font=("DejaVu Sans", 11, "bold"),
            fg=self.cpu_colors[0], bg=self.label_bg,
            padx=8, pady=3
        )
        self.cpu_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))

        self.mem_label = tk.Label(
            self.top_frame, text="MEM: --/-- GB",
            font=("DejaVu Sans", 11, "bold"),
            fg=self.mem_color, bg=self.label_bg,
            padx=8, pady=3
        )
        self.mem_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(3, 0))

        # === Бутон Always on Top ===
        self.btn_frame = tk.Frame(self, bg=self.bg)
        self.btn_frame.pack(fill=tk.X, padx=6, pady=(0, 2))

        self.topmost_btn = tk.Button(
            self.btn_frame,
            text="Always on Top: ON",
            font=("DejaVu Sans", 8),
            bg="#333333",
            fg="#e0e0e0",
            activebackground="#444444",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=6, pady=1,
            command=self._toggle_topmost
        )
        self.topmost_btn.pack(side=tk.LEFT)

        # === Canvas ===
        self.canvas = tk.Canvas(self, bg=self.bg, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=4, pady=(2, 4))
        self.canvas.bind("<Configure>", self._on_resize)

        self.after(200, self._update)

    def _get_num_threads(self):
        count = 0
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if line.startswith("processor"):
                        count += 1
        except Exception:
            count = 1
        return max(1, count)

    def _get_mem_total(self):
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        return int(line.split()[1])  # в KB
        except Exception:
            return 16 * 1024 * 1024  # fallback 16 GB
        return 16 * 1024 * 1024

    def _init_cpu(self):
        data = self._read_all_cpus()
        for i, (idle, total) in enumerate(data):
            if i < self.num_threads:
                self.prev_idles[i] = idle
                self.prev_totals[i] = total

    def _read_all_cpus(self):
        """Чете cpu0, cpu1, cpu2... от /proc/stat"""
        result = []
        try:
            with open("/proc/stat", "r") as f:
                for line in f:
                    if line.startswith("cpu") and not line.startswith("cpu "):
                        parts = line.split()
                        values = [int(x) for x in parts[1:9]]
                        idle = values[3] + values[4]  # idle + iowait
                        total = sum(values)
                        result.append((idle, total))
        except Exception:
            pass
        # Ако няма достатъчно, допълваме
        while len(result) < self.num_threads:
            result.append((0, 0))
        return result[:self.num_threads]

    def _get_cpu_percents(self):
        """Връща списък с % за всяка нишка"""
        data = self._read_all_cpus()
        percents = []
        for i, (idle, total) in enumerate(data):
            idle_delta = idle - self.prev_idles[i]
            total_delta = total - self.prev_totals[i]
            self.prev_idles[i] = idle
            self.prev_totals[i] = total

            if total_delta <= 0:
                percents.append(0.0)
            else:
                usage = 100.0 * (1.0 - idle_delta / total_delta)
                percents.append(max(0.0, min(100.0, usage)))
        return percents

    def _get_mem_info(self):
        """Връща (процент, used_gb, total_gb)"""
        mem_available = 0
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemAvailable:"):
                        mem_available = int(line.split()[1])
                        break
        except Exception:
            pass

        used_kb = self.mem_total_kb - mem_available
        used_gb = used_kb / (1024 * 1024)
        total_gb = self.mem_total_kb / (1024 * 1024)
        percent = 100.0 * used_kb / self.mem_total_kb if self.mem_total_kb else 0.0
        return percent, used_gb, total_gb

    def _toggle_topmost(self):
        self.topmost = not self.topmost
        self.attributes("-topmost", self.topmost)
        state = "ON" if self.topmost else "OFF"
        self.topmost_btn.config(text=f"Always on Top: {state}")

    def _on_resize(self, event=None):
        self._draw_graphs()

    def _draw_graphs(self):
        c = self.canvas
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 10 or h < 10:
            return

        pad = 4
        mid = h // 2
        graph_h = mid - pad * 2

        # --- CPU графика (горна) – 4 линии ---
        self._draw_multi_graph(
            c, 0, pad, w, graph_h,
            self.cpu_histories, self.cpu_colors, "CPU"
        )

        # --- Memory графика (долна) ---
        self._draw_single_graph(
            c, 0, mid + pad, w, graph_h,
            self.mem_history, self.mem_color, "MEM"
        )

    def _draw_single_graph(self, canvas, x0, y0, width, height, data, color, label):
        if height < 5 or width < 10:
            return

        canvas.create_rectangle(
            x0, y0, x0 + width, y0 + height,
            fill="#222222", outline="#333333", width=1
        )

        for pct in (0, 50, 100):
            y = y0 + height - (pct / 100.0) * height
            canvas.create_line(x0, y, x0 + width, y, fill=self.grid_color, dash=(2, 3))
            if height > 30:
                canvas.create_text(
                    x0 + 4, y - 1, text=f"{pct}",
                    anchor="sw", fill="#666666", font=("DejaVu Sans", 7)
                )

        n = len(data)
        if n < 2:
            return

        points = []
        for i, val in enumerate(data):
            x = x0 + (i / (n - 1)) * (width - 1)
            y = y0 + height - (val / 100.0) * height
            points.extend([x, y])

        if len(points) >= 4:
            canvas.create_line(*points, fill=color, width=1.5, smooth=False)

        if height > 20:
            canvas.create_text(
                x0 + 6, y0 + 4, text=label,
                anchor="nw", fill=color, font=("DejaVu Sans", 8, "bold")
            )

    def _draw_multi_graph(self, canvas, x0, y0, width, height, histories, colors, label):
        if height < 5 or width < 10:
            return

        canvas.create_rectangle(
            x0, y0, x0 + width, y0 + height,
            fill="#222222", outline="#333333", width=1
        )

        for pct in (0, 50, 100):
            y = y0 + height - (pct / 100.0) * height
            canvas.create_line(x0, y, x0 + width, y, fill=self.grid_color, dash=(2, 3))
            if height > 30:
                canvas.create_text(
                    x0 + 4, y - 1, text=f"{pct}",
                    anchor="sw", fill="#666666", font=("DejaVu Sans", 7)
                )

        # Рисуваме всяка нишка
        for hist, color in zip(histories, colors):
            n = len(hist)
            if n < 2:
                continue
            points = []
            for i, val in enumerate(hist):
                x = x0 + (i / (n - 1)) * (width - 1)
                y = y0 + height - (val / 100.0) * height
                points.extend([x, y])
            if len(points) >= 4:
                canvas.create_line(*points, fill=color, width=1.4, smooth=False)

        if height > 20:
            canvas.create_text(
                x0 + 6, y0 + 4, text=label,
                anchor="nw", fill=colors[0], font=("DejaVu Sans", 8, "bold")
            )

    def _update(self):
        # CPU – отделни нишки
        cpu_percents = self._get_cpu_percents()
        for i, p in enumerate(cpu_percents):
            self.cpu_histories[i].append(p)

        avg_cpu = sum(cpu_percents) / len(cpu_percents) if cpu_percents else 0.0

        # Memory
        mem_pct, used_gb, total_gb = self._get_mem_info()
        self.mem_history.append(mem_pct)

        # Етикети
        self.cpu_label.config(text=f"CPU: {avg_cpu:.0f}% ({self.num_threads} thr)")
        self.mem_label.config(text=f"MEM: {used_gb:.1f}/{total_gb:.1f} GB")

        self._draw_graphs()
        self.after(1000, self._update)


if __name__ == "__main__":
    app = CpuMemMonitor()
    app.mainloop()
