#!/bin/bash
#
# Process Monitor (/proc + elapsed time + memory + user + cmd + path)
#

ROOT="/proc"
DESH='|'
nl=$'\n'

RESULT="<Elapsed_time>${DESH}<PID>${DESH}<PPID>${DESH}<USER>${DESH}<MEM(kB)>${DESH}<MEMPERCENT>${DESH}<PATH>${DESH}<CMDLINE>${DESH}"

CLK_TCK=$(getconf CLK_TCK)
BOOTTIME=$(awk '/btime/ {print $2}' /proc/stat)
NOW=$(date +%s)

for PID in $(ls $ROOT | grep '^[0-9]\+$'); do
    DIR="${ROOT}/${PID}"
    STATUS="${DIR}/status"
    STAT="${DIR}/stat"

    [ -r "$STATUS" ] || continue
    [ -r "$STAT" ] || continue

    # ------------------------------------------------
    # CMDLINE
    # ------------------------------------------------
    CMDLINE=""
    if [ -r "${DIR}/cmdline" ]; then
        CMDLINE=$(tr '\000' ' ' < "${DIR}/cmdline")
    fi
    if [ -z "$CMDLINE" ]; then
        CMDLINE="[$(grep -m1 'Name:' "${STATUS}" | cut -f2)]"
    fi

    # ------------------------------------------------
    # PATH (실행 파일)
    # ------------------------------------------------
    RPATH=$(readlink "${DIR}/exe" 2>/dev/null)
    [ -z "$RPATH" ] && RPATH="[Unknown]"

    # ------------------------------------------------
    # UID / USER
    # ------------------------------------------------
    _UID=$(grep -m1 'Uid:' "${STATUS}" | awk '{print $2}')
    _USER="unknown"
    if [ -f /etc/passwd ]; then
        _USER=$(grep "x:$_UID:" /etc/passwd | cut -d: -f1)
        [ -z "$_USER" ] && _USER="unknown"
    fi

    # ------------------------------------------------
    # PPID
    # ------------------------------------------------
    P_PPID=$(awk '{print $4}' "$STAT" 2>/dev/null)
    [ -z "$P_PPID" ] && P_PPID="[Unknown]"

    # ------------------------------------------------
    # MEMORY USAGE (VmRSS in kB)
    # ------------------------------------------------
    MEM_KB="0"
    if grep -q "VmRSS:" "$STATUS"; then
        MEM_KB=$(grep "VmRSS:" "$STATUS" | awk '{print $2}')
    elif [ -r "${DIR}/statm" ]; then
        PAGE_SIZE=$(getconf PAGESIZE)
        RSS_PAGES=$(awk '{print $2}' "${DIR}/statm")
        MEM_KB=$(( (RSS_PAGES * PAGE_SIZE) / 1024 ))
    fi
    
    # ------------------------------------------------
    # MEMORY 점유울
    # ------------------------------------------------
    # 총 메모리 (kB)
    TOTAL_MEM=$(awk '/MemTotal/ {print $2}' /proc/meminfo)
    if [ "$TOTAL_MEM" -ne 0 ]; then
	    MEM_PERCENT=$(awk "BEGIN {printf \"%.2f\", ($MEM_KB/$TOTAL_MEM)*100}")
    else
	    MEM_PERCENT="[Unknown]"
    fi

    # ------------------------------------------------
    # ELAPSED TIME (수행 시간)
    # ------------------------------------------------
    START_TICKS=$(awk '{print $22}' "$STAT" 2>/dev/null)
    if [ -n "$START_TICKS" ] && [ -n "$CLK_TCK" ] && [ -n "$BOOTTIME" ]; then
        PROC_START_EPOCH=$(echo "$BOOTTIME + ($START_TICKS / $CLK_TCK)" | bc -l)
        ELAPSED_SEC=$(echo "$NOW - $PROC_START_EPOCH" | bc -l)

        # 안전 처리: 비어있거나 음수면 [Unknown]
        if [ -z "$ELAPSED_SEC" ] || (( $(echo "$ELAPSED_SEC < 0" | bc -l) )); then
            ELAPSED_TIME="[Unknown]"
        else
            ELAPSED_SEC_INT=${ELAPSED_SEC%.*}
            HOURS=$((ELAPSED_SEC_INT / 3600))
            MINUTES=$(( (ELAPSED_SEC_INT % 3600) / 60 ))
            SECONDS=$((ELAPSED_SEC_INT % 60))
            ELAPSED_TIME=$(printf "%02d:%02d:%02d" $HOURS $MINUTES $SECONDS)
        fi
    else
        ELAPSED_TIME="[Unknown]"
    fi

    # ------------------------------------------------
    # OUTPUT
    # ------------------------------------------------
    LINE="${ELAPSED_TIME}${DESH}${PID}${DESH}${P_PPID}${DESH}${_USER}${DESH}${MEM_KB}${DESH}${MEM_PERCENT}${DESH}${RPATH}${DESH}${CMDLINE}"
    RESULT="${RESULT}${nl}${LINE}"
done

echo "$RESULT"
