import subprocess
import os
import time
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from typing import List, Dict

# [Data Model] 프로세스 정보 (Bash 출력 순서 1:1 매핑)
@dataclass
class ProcessInfo:
    elapsed_time: str   # 1. 수행 시간
    pid: int            # 2. PID
    user: str           # 3. 사용자
    mem_kb: int         # 4. 메모리 (KB)
    mem_percent: float  # 5. 메모리 (%)
    path: str           # 6. 실행 경로
    cmdline: str        # 7. 명령어
    
    @property
    def cpu_percent(self): 
        # 현재 Bash 스크립트에는 CPU 계산 로직이 없으므로 0.0 반환
        return 0.0 
    
    @property
    def name(self):
        """
        차트 그리기용 프로세스 이름 추출 (경로 제외, 인자 제외)
        예: '/usr/bin/python3 ./main.py' -> 'python3'
        """
        if not self.cmdline:
            return "unknown"
        # 1. 명령어의 첫 부분(경로 포함) 가져오기
        full_path = self.cmdline.split()[0]
        # 2. 경로 떼고 파일명만 리턴
        return os.path.basename(full_path)

# [Data Manager] Bash 스크립트 실행 및 파싱
class SystemDataManager:
    def __init__(self, script_path="./parse_prc.sh"):
        self.script_path = script_path
        
        if not os.path.exists(self.script_path):
            print(f"[경고] '{self.script_path}' 파일을 찾을 수 없습니다.")

    def get_all_processes(self) -> List[ProcessInfo]:
        process_list = []
        
        # 파일 없으면 빈 리스트 리턴
        if not os.path.exists(self.script_path):
            return []

        try:
            # 1. Bash 스크립트 실행
            result = subprocess.run(
                [self.script_path], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True, 
                check=True
            )
            
            # 2. 줄 단위 파싱
            lines = result.stdout.strip().split('\n')
            
            for line in lines:
                if not line: continue
                
                # 구분자(|)로 분리
                parts = line.split('|')
                
                # 데이터 필드가 7개 미만이면 건너뜀 (안전장치)
                if len(parts) < 7:
                    continue
                
                try:
                    p_info = ProcessInfo(
                        elapsed_time=parts[0],
                        pid=int(parts[1]),
                        user=parts[2],
                        mem_kb=int(parts[3]),
                        mem_percent=float(parts[4]) if parts[4] != "[Unknown]" else 0.0,
                        path=parts[5],
                        cmdline=parts[6]
                    )
                    process_list.append(p_info)
                    
                except ValueError:
                    # 헤더나 잘못된 데이터 포맷 무시
                    continue
                    
        except subprocess.CalledProcessError as e:
            print(f"[Error] 스크립트 실행 중 에러: {e}")
        except Exception as e:
            print(f"[Error] 알 수 없는 에러: {e}")
            
        return process_list

# [Engine] 다이어그램 로직 (통계 + 히스토리 + 목록)
class ProcessEngine:
    def __init__(self, data_manager: SystemDataManager):
        self.data_manager = data_manager
        self.history = deque(maxlen=100) 

    # [기능 1] 모든 프로세스 목록 반환
    def get_running_processes(self) -> List[ProcessInfo]:
        return self.data_manager.get_all_processes()

    # [기능 2] 사용자별 통계 계산 (100% 초과 방지 로직 추가 (shared memory))
    def calculate_stats_by_user(self) -> Dict[str, Dict[str, float]]:
        raw_data = self.data_manager.get_all_processes()
        stats = defaultdict(lambda: {"mem_sum": 0.0, "count": 0})
        
        for proc in raw_data:
            stats[proc.user]["mem_sum"] += proc.mem_percent
            stats[proc.user]["count"] += 1
            
        # [수정된 부분] 보기 좋게 다듬기 (Formatting)
        final_stats = {}
        for user, data in stats.items():
            mem_val = data["mem_sum"]
            
            # 1. 100%가 넘으면 100%로 고정 (Visual Clamping)
            if mem_val > 100.0:
                mem_val = 100.0
            
            final_stats[user] = {
                "mem": round(mem_val, 2), # 소수점 2자리 반올림
                "count": data["count"]
            }
            
        return final_stats

    # [기능 3] Top N 프로세스 비교 (현재 vs 5초 전) --> 시간 계산 대신 가장 최근 기록(Last In)을 비교 대상으로 사용
    def get_top_processes_comparison(self, top_n=5):
        # 1. 현재 데이터 수집
        current_procs = self.data_manager.get_all_processes()
        current_time = time.time()
        current_counts = Counter([p.name for p in current_procs])
        
        # 2. 과거 데이터 가져오기 (History의 가장 마지막 요소가 직전 루프의 데이터임)
        past_counts = {}
        if self.history:
            # history[-1] 은 (timestamp, counts_dict) 튜플
            _, past_counts = self.history[-1]
        
        # 3. Top N 추출
        top_list = current_counts.most_common(top_n)
        
        # 4. 결과 조합
        result = []
        for name, curr_cnt in top_list:
            past_cnt = past_counts.get(name, 0)
            result.append({
                "name": name,
                "current": curr_cnt,
                "past": past_cnt,
                "diff": curr_cnt - past_cnt
            })
            
        # 5. 현재 상태 저장
        self.history.append((current_time, dict(current_counts)))
        
        return result
    
# [Main] 실행 및 출력
if __name__ == "__main__":
    # 1. 초기화 (쉘 스크립트 경로 지정 및 엔진 생성)
    # 실행 권한 필수: chmod +x parse_prc.sh
    dm = SystemDataManager("./parse_prc.sh")
    engine = ProcessEngine(dm)

    print(" 데이터를 불러오는 중입니다... 잠시만 기다려주세요.")

    # [섹션 1] 모든 프로세스 목록 출력
    all_procs = engine.get_running_processes()
    
    header = f"{'TIME':<10} | {'PID':<6} | {'USER':<10} | {'MEM%':<6} | {'CMD'}"
    print("\n" + "=" * 100)
    print(f" [1] 전체 프로세스 목록 (총 {len(all_procs)}개)")
    print("=" * 100)
    print(header)
    print("-" * 100)

    for p in all_procs:
        # CMD가 너무 길면 잘라서 출력 (화면 깨짐 방지)
        cmd_short = (p.cmdline[:60] + '..') if len(p.cmdline) > 60 else p.cmdline
        line = f"{p.elapsed_time:<10} | {p.pid:<6} | {p.user:<10} | {p.mem_percent:<6.2f} | {cmd_short}"
        print(line)

    print("-" * 100)


    # 사용자별 통계 출력 (다이어그램 1번 기능)
    # 엔진에서 사용자별로 그룹화된 데이터를 받아옵니다.
    user_stats = engine.calculate_stats_by_user()
    
    # 보기 좋게 메모리 사용량 순으로 정렬 (내림차순)
    sorted_stats = sorted(user_stats.items(), key=lambda item: item[1]['mem'], reverse=True)

    print("\n" + "=" * 100)
    print(" 2. 사용자별 리소스 사용 통계 (donut chart)")
    print("=" * 100)
    print(f"{'USER':<15} | {'COUNT':<6} | {'MEM TOTAL (%)'}")
    print("-" * 100)

    for user, stat in sorted_stats:
        # stat 구조: {'mem': 12.5, 'count': 5, ...}
        print(f"{user:<15} | {stat['count']:<6} | {stat['mem']:.2f}%")
    print("-" * 100)


    # 1차 수집 (과거 데이터 생성용)
    engine.get_top_processes_comparison()
    time.sleep(5) 
    
    # 2차 수집 (실제 비교)
    print("\n" + "="*80)
    print(" Top 5 프로세스 비교 (디자이너의 막대 차트용)")
    print("="*80)
    print(f"{'PROCESS NAME':<20} | {'CURRENT (Green)':<15} | {'PAST (Yellow)':<15} | {'DIFF'}")
    print("-" * 80)
    
    # 여기서 리턴된 데이터로 차트를 그리면 됩니다.
    chart_data = engine.get_top_processes_comparison(top_n=5)
    
    for item in chart_data:
        diff_str = f"(+{item['diff']})" if item['diff'] > 0 else f"({item['diff']})"
        print(f"{item['name']:<20} | {item['current']:<15} | {item['past']:<15} | {diff_str}")
        
    print("-" * 80)