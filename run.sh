#!/bin/bash
# =====================================================================
# SCRIPT CHAY DO AN TOT NGHIEP
# Tu dong hoa cau hinh va kiem soat tuan thu an ninh mang
# =====================================================================
set -e
cd "$(dirname "$0")"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

banner() { echo -e "\n${CYAN}==== $1 ====${NC}\n"; }
ok() { echo -e "${GREEN}[OK]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

ansible_run() {
    python3 -c "
import subprocess, sys
r = subprocess.run(['ansible-playbook', '-i', 'inventory/hosts.yml'] + sys.argv[1:], capture_output=True, text=True, timeout=600)
print(r.stdout)
if r.returncode != 0: print(r.stderr); sys.exit(r.returncode)
" "$@"
}

case "${1:-help}" in
  lab-up)
    banner "KHOI TAO LAB (6 thiet bi)"
    sudo clab deploy -t lab/topo.clab.yml --reconfigure
    sleep 5
    # Setup FRR containers
    for node in edge1 leaf3; do
        cname="clab-datn-lab-${node}"
        docker exec "$cname" sh -c 'echo "PermitRootLogin yes" >> /etc/ssh/sshd_config && killall sshd 2>/dev/null; /usr/sbin/sshd'
        docker exec "$cname" sh -c 'mkdir -p /root/.ssh && chmod 700 /root/.ssh'
        docker cp ~/.ssh/id_ed25519.pub "${cname}:/root/.ssh/authorized_keys"
        docker exec "$cname" chown root:root /root/.ssh/authorized_keys
        docker exec "$cname" chmod 600 /root/.ssh/authorized_keys
        docker exec "$cname" sh -c '/usr/lib/frr/bgpd -d -F traditional -A 127.0.0.1 2>/dev/null'
        ok "${node}: SSH + BGP"
    done
    ok "Lab san sang"
    ;;

  lab-down)
    banner "XOA LAB"
    sudo clab destroy -t lab/topo.clab.yml --cleanup
    ok "Lab da xoa"
    ;;

  ping)
    banner "KIEM TRA KET NOI (Ansible Ping)"
    ansible_run -m ping -i inventory/hosts.yml all
    ;;

  deploy)
    banner "TRIEN KHAI CAU HINH (deploy.yml)"
    ansible_run deploy.yml -v
    ok "Deploy hoan tat"
    ;;

  harden)
    banner "CHUAN HOA AN NINH (harden.yml)"
    ansible_run harden.yml -v
    ok "Hardening hoan tat"
    ;;

  backup)
    banner "SAO LUU CAU HINH (backup.yml)"
    ansible_run backup.yml -v
    ok "Backup hoan tat"
    ;;

  all)
    banner "CHAY TOAN BO (deploy + harden + backup)"
    $0 deploy
    $0 harden
    $0 backup
    ok "Tat ca playbook da chay thanh cong"
    ;;

  scan)
    banner "QUET AN NINH MANG"
    python3 security/attacks/network_scan.py --output scan_result.json
    ;;

  score)
    banner "CHAM DIEM TUAN THU"
    shift || true
    case "${1:-golden}" in
      golden)  python3 compliance/tools/score.py --sot sot/devices.yaml --policy compliance/policy/cis_rules.yaml --configs compliance/configs/golden ;;
      after)   python3 compliance/tools/score.py --sot sot/devices.yaml --policy compliance/policy/cis_rules.yaml --configs compliance/configs/after ;;
      live)    python3 compliance/tools/score.py --sot sot/devices.yaml --policy compliance/policy/cis_rules.yaml --configs compliance/configs/live ;;
      compare) python3 compliance/tools/score.py --sot sot/devices.yaml --policy compliance/policy/cis_rules.yaml --compare compliance/configs/golden compliance/configs/after ;;
    esac
    ;;

  dashboard)
    banner "KHOI DONG DASHBOARD"
    echo "Truy cap: http://localhost:5000"
    python3 dashboard/app.py
    ;;

  demo)
    banner "DEMO TOAN BO HE THONG"
    echo "1. Deploy cau hinh..."
    $0 deploy
    echo ""
    echo "2. Cham diem TRUOC hardening..."
    $0 score golden
    echo ""
    echo "3. Ap dung hardening..."
    $0 harden
    echo ""
    echo "4. Backup cau hinh..."
    $0 backup
    echo ""
    echo "5. Cham diem SAU hardening..."
    $0 score after
    echo ""
    echo "6. So sanh truoc/sau..."
    $0 score compare
    echo ""
    echo "7. Quet an ninh..."
    $0 scan
    echo ""
    ok "Demo hoan tat! Khoi dong dashboard: ./run.sh dashboard"
    ;;

  help|*)
    echo "=========================================="
    echo "  DO AN TOT NGHIEP — QUAN LY AN NINH MANG"
    echo "=========================================="
    echo ""
    echo "Cach dung: ./run.sh <lenh>"
    echo ""
    echo "  lab-up     Khoi tao lab 6 thiet bi (can sudo)"
    echo "  lab-down   Xoa lab"
    echo "  ping       Kiem tra ket noi Ansible"
    echo "  deploy     Trien khai cau hinh co ban + dinh tuyen + VLAN"
    echo "  harden     Ap dung chuan hoa an ninh CIS"
    echo "  backup     Sao luu cau hinh thiet bi"
    echo "  all        Chay deploy + harden + backup"
    echo "  scan       Quet an ninh mang (nmap/python)"
    echo "  score      Cham diem tuan thu (golden|after|live|compare)"
    echo "  dashboard  Khoi dong web dashboard (port 5000)"
    echo "  demo       Chay demo toan bo he thong"
    echo ""
    ;;
esac
