import subprocess
import os
import time
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from typing import List, Dict

# =========================================================
# [Layer 1: Data Model] 데이터 전송 객체 (DTO)
# 설계도 상에서 'SystemDataManager'가 'Engine'에게 넘겨주는 데이터 구조입니다.
# =========================================================
@dataclass
class ProcessInfo:
    """
    개별 프로세스의 정보를 담는 객체입니다.
    Bash 스크립트의 출력 결과(Pipe로 구분된 문자열)를 이 객체로 매핑합니다.
    """
    elapsed_time: str   # 실행 시간 (예: 00:05:12)
    pid: int            # Process ID
    ppid: int           # Parent Process ID (Bash 스크립트 업데이트로 추가됨)
    user: str           # 실행한 사용자 (root, user 등)
    mem_kb: int         # 물리 메모리 사용량 (KB)
    mem_percent: float  # 물리 메모리 점유율 (%)
    path: str           # 실행 파일의 절대 경로
    cmdline: str        # 실행 명령어 (Arguments 포함)
    
    @property
    def cpu_percent(self): 
        """현재 기술적 한계(Bash 스크립트)로 CPU 사용량은 0.0을 반환합니다."""
        return 0.0 
    
    @property
    def name(self):
        """
        [UI 렌더링용] 차트에 표시할 짧은 프로세스 이름을 추출합니다.
        예: '/usr/bin/python3 ./main.py' -> 'python3'
        """
        if not self.cmdline:
            return "unknown"
        # 명령어의 첫 부분(경로 포함)만 잘라서 파일명 추출
        full_path = self.cmdline.split()[0]
        return os.path.basename(full_path)


# =========================================================
# [Layer 2: Data Manager] 데이터 접근 계층 (DAO)
# 설계도: SystemDataManager
# 역할: Bash 스크립트를 실행하고, Raw 데이터를 가져와서 객체로 변환합니다.
# =========================================================
class SystemDataManager:
    def __init__(self, script_filename="parse_prc.sh"):
        # [안정성 확보] 실행 위치와 관계없이 스크립트를 찾을 수 있도록 절대 경로를 사용합니다.
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.script_path = os.path.join(base_dir, script_filename)
        
        if not os.path.exists(self.script_path):
            print(f"[Critical Error] '{self.script_path}' 스크립트를 찾을 수 없습니다.")

    def get_all_processes(self) -> List[ProcessInfo]:
        """
        [설계도 공통] get_all_processes() 메시지 구현
        실제 OS의 프로세스 정보를 수집하여 List<ProcessInfo> 형태로 반환합니다.
        """
        process_list = []
        
        if not os.path.exists(self.script_path):
            return []

        try:
            # 1. 외부 Bash 스크립트 실행 (subprocess 모듈 사용)
            result = subprocess.run(
                [self.script_path], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True, 
                check=True
            )
            
            # 2. 결과 파싱 (Line by Line)
            lines = result.stdout.strip().split('\n')
            
            for line in lines:
                if not line: continue
                
                parts = line.split('|')
                
                # [유효성 검사] 데이터 필드가 8개 미만이면 파싱 불가 (PPID 포함 여부 확인)
                if len(parts) < 8:
                    continue
                
                try:
                    # [매핑] Bash 출력 순서: TIME | PID | PPID | USER | MEM | MEM% | PATH | CMD
                    p_info = ProcessInfo(
                        elapsed_time=parts[0],
                        pid=int(parts[1]),
                        ppid=int(parts[2]),      # PPID 매핑
                        user=parts[3],
                        mem_kb=int(parts[4]),
                        mem_percent=float(parts[5]) if parts[5] != "[Unknown]" else 0.0,
                        path=parts[6],
                        cmdline=parts[7]
                    )
                    process_list.append(p_info)
                    
                except ValueError:
                    continue # 수치 변환 실패 시 해당 라인 무시
                    
        except Exception as e:
            print(f"[Error] 데이터 수집 중 예외 발생: {e}")
            
        return process_list


# =========================================================
# [Layer 3: Engine] 비즈니스 로직 계층
# 설계도: ProcessEngine (UserActivityEngine / ProcessStatsEngine 통합)
# 역할: 데이터를 가공, 집계, 비교(History 관리)하여 UI에 전달합니다.
# =========================================================
class ProcessEngine:
    def __init__(self, data_manager: SystemDataManager):
        self.data_manager = data_manager
        
        # [다이어그램 2번 구현을 위한 상태 저장소]
        # 과거 데이터를 저장하기 위해 Deque(이중 연결 리스트)를 사용합니다.
        # maxlen=100: 최신 100개의 스냅샷만 유지하고 오래된 것은 자동 삭제 (메모리 관리)
        self.history = deque(maxlen=100) 

    # ---------------------------------------------------------
    # [다이어그램 3번] 단순 목록 조회 기능
    # UI 요청: get_running_processes()
    # ---------------------------------------------------------
    def get_running_processes(self) -> List[ProcessInfo]:
        """현재 실행 중인 모든 프로세스 목록을 반환합니다. (테이블/리스트 뷰용)"""
        return self.data_manager.get_all_processes()

    # ---------------------------------------------------------
    # [다이어그램 1번] 사용자별 통계 집계 기능
    # UI 요청: calculate_stats_by_user()
    # ---------------------------------------------------------
    def calculate_stats_by_user(self) -> Dict[str, Dict[str, float]]:
        """
        사용자(User)별로 메모리 점유율을 합산하여 반환합니다. (도넛 차트용)
        반환 형식: {'root': {'mem': 12.5, 'count': 5}, ...}
        """
        raw_data = self.data_manager.get_all_processes()
        stats = defaultdict(lambda: {"mem_sum": 0.0, "count": 0})
        
        # 1. 그룹화 및 합산 로직
        for proc in raw_data:
            stats[proc.user]["mem_sum"] += proc.mem_percent
            stats[proc.user]["count"] += 1
            
        # 2. 데이터 후처리 (Formatting)
        final_stats = {}
        for user, data in stats.items():
            mem_val = data["mem_sum"]
            
            # [UX 보정] 리눅스 Shared Memory 특성상 합산이 100%를 넘을 수 있음.
            # 사용자 혼란을 방지하기 위해 시각적으로 최대 100%로 보정(Clamping)함.
            if mem_val > 100.0:
                mem_val = 100.0
            
            final_stats[user] = {
                "mem": round(mem_val, 2), # 소수점 2자리 반올림
                "count": data["count"]
            }
            
        return final_stats

    # ---------------------------------------------------------
    # [다이어그램 2번] 과거 데이터 비교 및 변동 감지 기능
    # UI 요청: get_top_processes_comparison() -> (디자이너의 막대 차트 대응)
    # ---------------------------------------------------------
    def get_top_processes_comparison(self, top_n=5):
        """
        현재 가장 많이 실행된 프로세스 Top N을 뽑고, 
        과거(직전 루프) 데이터와 비교하여 증감(Diff)을 계산합니다.
        """
        # 1. 현재 데이터 수집 (Live Data)
        current_procs = self.data_manager.get_all_processes()
        current_time = time.time()
        
        # 프로세스 이름별 개수 카운팅 (예: chrome: 10, bash: 2)
        current_counts = Counter([p.name for p in current_procs])
        
        # 2. 과거 데이터 조회 (History)
        past_counts = {}
        if self.history:
            # 히스토리의 가장 마지막 요소(-1)가 직전 루프의 데이터입니다.
            # (timestamp, counts_dict) 튜플 형태
            _, past_counts = self.history[-1]
        
        # 3. 현재 기준 Top N 추출
        top_list = current_counts.most_common(top_n)
        
        # 4. 비교 로직 (Comparison)
        result = []
        for name, curr_cnt in top_list:
            # 과거 기록이 없으면 0으로 처리 (get 메서드 사용)
            past_cnt = past_counts.get(name, 0)
            
            result.append({
                "name": name,          # 프로세스 이름
                "current": curr_cnt,   # 현재 개수 (초록 막대)
                "past": past_cnt,      # 과거 개수 (노란 막대)
                "diff": curr_cnt - past_cnt # 변동량
            })
            
        # 5. 현재 상태를 히스토리에 저장 (다음 비교를 위해)
        self.history.append((current_time, dict(current_counts)))
        
        return result

# =========================================================
# [Main Entry Point] 테스트 및 실행
# =========================================================
if __name__ == "__main__":
    # Dependency Injection (의존성 주입)
    # SystemDataManager를 Engine에 주입하여 결합도를 낮춤
    dm = SystemDataManager("parse_prc.sh")
    engine = ProcessEngine(dm)

    print(" 데이터를 불러오는 중입니다... 잠시만 기다려주세요.")

    # ... (이하 테스트 출력 코드는 동일) ...
    # 필요하다면 이전 코드의 __main__ 내용을 여기에 복사해서 쓰시면 됩니다.
    # 팀장님 설명용으로는 위 클래스 구조가 중요합니다.