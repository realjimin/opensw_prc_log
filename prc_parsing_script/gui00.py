import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np

# 사용자 제공 백엔드 모듈 임포트
# (같은 디렉토리에 parsing_engine.py가 있어야 함)
from parsing_engine import SystemDataManager, ProcessEngine

# ==========================================
# Configuration & Styles
# ==========================================
BG_COLOR = "#454444"       # 전체 배경 검정
FG_COLOR = "#FFFFFF"       # 기본 텍스트 흰색
CARD_BG = "#454444"        # 카드 배경 (필요시 회색조로 변경 가능)
ACCENT_BLUE = "#007bff"    # 강조 색상 (파랑)
CHART_COLORS = ['#ff6b6b', '#feca57', '#48dbfb', '#ff9ff3', '#54a0ff', '#5f27cd'] # 도넛 차트 색상 팔레트

# Matplotlib 다크 모드 설정
plt.style.use('dark_background')
plt.rcParams['axes.facecolor'] = BG_COLOR
plt.rcParams['figure.facecolor'] = BG_COLOR
plt.rcParams['text.color'] = FG_COLOR
plt.rcParams['axes.labelcolor'] = FG_COLOR
plt.rcParams['xtick.color'] = FG_COLOR
plt.rcParams['ytick.color'] = FG_COLOR
plt.rcParams['font.size'] = 9

class PLogSightApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PLog_sight")
        self.root.geometry("1200x800")
        self.root.configure(bg=BG_COLOR)

        # 1. 백엔드 엔진 초기화
        # 실행 권한이 있는 parse_prc.sh가 같은 경로에 있어야 데이터가 나옵니다.
        self.dm = SystemDataManager("./parse_prc.sh")
        self.engine = ProcessEngine(self.dm)

        # 2. UI 레이아웃 구성
        self._setup_layout()
        
        # 3. 데이터 자동 갱신 시작 (5초 주기)
        self.update_data()

    def _setup_layout(self):
        # --- Header ---
        header_frame = tk.Frame(self.root, bg=BG_COLOR, height=50)
        header_frame.pack(side="top", fill="x", padx=20, pady=10)
        
        # 로고/제목
        title_lbl = tk.Label(header_frame, text="PLog_sight", font=("Arial", 18, "bold"), 
                             bg=BG_COLOR, fg=FG_COLOR, anchor="w")
        title_lbl.pack(side="left")
        
        # 검색 버튼
        search_btn = tk.Button(header_frame, text="Search", bg="#ffffff", fg="black", 
                               font=("Arial", 10), width=10)
        search_btn.pack(side="right")

        # --- Main Content Area (Grid System) ---
        content_frame = tk.Frame(self.root, bg=BG_COLOR)
        content_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        content_frame.columnconfigure(0, weight=1)
        content_frame.columnconfigure(1, weight=1)
        content_frame.rowconfigure(0, weight=4) # 차트 영역
        content_frame.rowconfigure(1, weight=3) # 리스트 영역

        # --- 1. Top Left: User Activities (Donut Chart) ---
        self.frame_left = tk.LabelFrame(content_frame, text="User Activities", 
                                        bg=BG_COLOR, fg=FG_COLOR, font=("Arial", 12, "bold"), bd=1, relief="solid")
        self.frame_left.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Matplotlib Figure 생성
        self.fig_donut, self.ax_donut = plt.subplots(figsize=(5, 4))
        self.canvas_donut = FigureCanvasTkAgg(self.fig_donut, master=self.frame_left)
        self.canvas_donut.get_tk_widget().pack(fill="both", expand=True)

        # --- 2. Top Right: Most Executed processes (Bar Chart) ---
        self.frame_right = tk.LabelFrame(content_frame, text="Most Executed processes", 
                                         bg=BG_COLOR, fg=FG_COLOR, font=("Arial", 12, "bold"), bd=1, relief="solid")
        self.frame_right.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        
        self.fig_bar, self.ax_bar = plt.subplots(figsize=(5, 4))
        self.canvas_bar = FigureCanvasTkAgg(self.fig_bar, master=self.frame_right)
        self.canvas_bar.get_tk_widget().pack(fill="both", expand=True)

        # --- 3. Bottom: Real time Log Events (Table) ---
        self.frame_bottom = tk.Frame(content_frame, bg=BG_COLOR)
        self.frame_bottom.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=5, pady=20)
        
        lbl_list = tk.Label(self.frame_bottom, text="Real time Log Events", 
                            font=("Arial", 14, "bold"), bg=BG_COLOR, fg=FG_COLOR, anchor="w")
        lbl_list.pack(fill="x", pady=(0, 10))

        # Treeview 스타일링 (Dark Theme)
        style = ttk.Style()
        style.theme_use("clam") # 기본 테마 변경
        style.configure("Treeview", 
                        background="black", 
                        foreground="white", 
                        fieldbackground="black", 
                        rowheight=25,
                        borderwidth=0,
                        font=("Arial", 10))
        style.configure("Treeview.Heading", 
                        background="black", 
                        foreground="white", 
                        font=("Arial", 10, "bold"),
                        borderwidth=1)
        style.map("Treeview", background=[("selected", "#333333")])

        # Treeview 생성
        columns = ("PID", "PPID", "TIME", "USER", "MEM", "COMMAND", "PATH")
        self.tree = ttk.Treeview(self.frame_bottom, columns=columns, show="headings", height=8)
        
        # 컬럼 설정
        col_widths = [60, 60, 80, 100, 80, 200, 100]
        for col, width in zip(columns, col_widths):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width, anchor="center")
        
        # COMMAND는 왼쪽 정렬이 보기 좋음
        self.tree.column("COMMAND", anchor="w")
        
        # 스크롤바 추가
        scrollbar = ttk.Scrollbar(self.frame_bottom, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def update_data(self):
        """주기적으로 데이터를 갱신하고 차트를 다시 그립니다."""
        # 1. 사용자별 통계 (도넛 차트) 갱신
        user_stats = self.engine.calculate_stats_by_user()
        self._draw_donut_chart(user_stats)

        # 2. 프로세스 비교 (바 차트) 갱신
        # 비교를 위해 내부적으로 history를 쌓으므로 주기적 호출 필수
        proc_comparison = self.engine.get_top_processes_comparison(top_n=5)
        self._draw_bar_chart(proc_comparison)

        # 3. 리스트 (트리뷰) 갱신
        all_procs = self.engine.get_running_processes()
        self._update_process_list(all_procs)

        # 5초(5000ms) 뒤에 다시 호출
        self.root.after(5000, self.update_data)

    def _draw_donut_chart(self, stats):
        self.ax_donut.clear()
        
        if not stats:
            self.ax_donut.text(0.5, 0.5, "No Data", ha='center', va='center', color='white')
            self.canvas_donut.draw()
            return

        # 데이터 가공
        labels = []
        sizes = []
        for user, info in stats.items():
            labels.append(user)
            sizes.append(info['mem'])

        # 도넛 차트 그리기
        wedges, texts = self.ax_donut.pie(
            sizes, 
            labels=None, # 레이블은 범례로 뺌
            startangle=90, 
            colors=CHART_COLORS[:len(labels)],
            wedgeprops=dict(width=0.4) # 도넛 모양(가운데 구멍)
        )
        
        # 범례 추가 (오른쪽)
        self.ax_donut.legend(wedges, labels, title="Users", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))
        self.canvas_donut.draw()

    def _draw_bar_chart(self, data):
        self.ax_bar.clear()
        
        if not data:
            self.ax_bar.text(0.5, 0.5, "Collecting History...", ha='center', va='center', color='white')
            self.canvas_bar.draw()
            return

        names = [item['name'] for item in data]
        current_vals = [item['current'] for item in data]
        past_vals = [item['past'] for item in data]

        x = np.arange(len(names))
        width = 0.35

        # 그룹화된 바 차트
        # 현재(초록색 계열), 과거(노란색 계열) - 이미지와 유사하게
        rects1 = self.ax_bar.bar(x - width/2, current_vals, width, label='Current', color='#4cd137')
        rects2 = self.ax_bar.bar(x + width/2, past_vals, width, label='Past', color='#fbc531')

        self.ax_bar.set_xticks(x)
        self.ax_bar.set_xticklabels(names)
        self.ax_bar.legend()
        
        # 그리드 선 (가로만)
        self.ax_bar.grid(axis='y', linestyle='-', alpha=0.3)
        # 테두리 제거 (디자인 맞춤)
        self.ax_bar.spines['top'].set_visible(False)
        self.ax_bar.spines['right'].set_visible(False)
        self.ax_bar.spines['left'].set_visible(False)

        self.canvas_bar.draw()

    def _update_process_list(self, procs):
        # 기존 목록 삭제
        for i in self.tree.get_children():
            self.tree.delete(i)
            
        # 데이터 삽입 (PPID는 데이터에 없으므로 임의값 0 또는 PID-1 처리)
        for p in procs:
            # PID, PPID, TIME, USER, MEM, COMMAND, PATH
            # 엔진 데이터: elapsed_time, pid, user, mem_kb, mem_percent, path, cmdline
            
            # PPID는 현재 쉘스크립트 파싱 결과에 없어서 0으로 표기하거나 추후 추가 필요
            
            # cmdline이 너무 길면 자르기
            cmd_display = p.cmdline if len(p.cmdline) < 40 else p.cmdline[:37] + "..."
            
            # Treeview 순서: PID, PPID, TIME, USER, MEM, COMMAND, PATH
            self.tree.insert("", "end", values=(
                p.pid,
                p.ppid,
                p.elapsed_time,
                p.user,
                f"{p.mem_percent}%",
                cmd_display,
                p.path # Path 추가
            ))

if __name__ == "__main__":
    root = tk.Tk()
    app = PLogSightApp(root)
    root.mainloop()
