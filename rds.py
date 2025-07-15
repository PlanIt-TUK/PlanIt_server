"""
rds.py – Data Access Layer for Planit (FastAPI) 2025‑07‑14

스키마 변화
────────────────────────────────────────────
* task_table
    - task_start / task_end : DATE
    - task_state           : ENUM('TODO','DOING','DONE')
    - color                : TINYINT(0‑11)
    - team_name / user_email UNIQUE 해제
* board_table
    - team_name UNIQUE 해제, 컬럼명 board_name 사용
* member_table
    - user_owner → TINYINT(1)  (0=MEMBER, 1=OWNER)
    - team_name / user_email 단독 UNIQUE 삭제,
      대신 (team_name, user_email) 복합 UNIQUE
* 나머지 테이블 구조는 유지
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple

import pymysql
from pymysql.cursors import DictCursor

# ────────────────────────────────
# 0.  DB helpers
# ────────────────────────────────


def init_db() -> Tuple[pymysql.Connection, DictCursor]:
    """환경 변수 기반 커넥션 + DictCursor 반환"""
    conn = pymysql.connect(
        host=os.environ["RDS_HOST"],
        port=int(os.getenv("RDS_PORT", 3306)),
        user=os.environ["RDS_USER"],
        password=os.environ["RDS_PASSWORD"],
        database=os.environ["RDS_DB"],
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
    )
    return conn, conn.cursor()


def close_db(conn, cur):  # type: ignore[valid-type]
    try:
        cur and cur.close()
    finally:
        conn and conn.close()


# ────────────────────────────────
# 1.  Setting
# ────────────────────────────────


def load_setting_from_db(*, cursor, table_name: str = "setting_table") -> Tuple[str, str]:
    cursor.execute(f"SELECT kakao_key, google_key FROM {table_name} LIMIT 1")
    row = cursor.fetchone()
    if not row:
        raise RuntimeError("setting_table is empty")
    return row["kakao_key"], row["google_key"]


# ────────────────────────────────
# 2.  User
# ────────────────────────────────


def add_user_to_db(
    *,
    connection,
    cursor,
    user_email: str,
    user_nickname: str,
    user_image: str,
    table_name: str = "user_table",
):
    cursor.execute(
        f"""
        INSERT INTO {table_name} (user_email, user_nickname, user_image)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            user_nickname = VALUES(user_nickname),
            user_image    = VALUES(user_image)
        """,
        (user_email, user_nickname, user_image),
    )
    connection.commit()


def load_user_from_db(
    *, cursor, user_email: str, table_name: str = "user_table"
) -> Dict[str, Any] | None:
    cursor.execute(f"SELECT * FROM {table_name} WHERE user_email=%s", (user_email,))
    return cursor.fetchone()


def delete_user_from_db(
    *,
    connection,
    cursor,
    user_email: str,
    user_table: str = "user_table",
    task_table: str = "task_table",
    member_table: str = "member_table",
):
    
    """
    db유저 삭제시
      1) member_table  팀 탈퇴
      2) task_table    담당자 해제
      3) user_table    삭제
    """

    cursor.execute(f"DELETE FROM {member_table} WHERE user_email=%s", (user_email,))
    cursor.execute(
        f"UPDATE {task_table} SET user_email='' WHERE user_email=%s", (user_email,)
    )
    cursor.execute(f"DELETE FROM {user_table} WHERE user_email=%s", (user_email,))
    connection.commit()


# ────────────────────────────────
# 3.  Task
# ────────────────────────────────


def add_task_to_db(
    *,
    connection,
    cursor,
    team_name: str,
    task_name: str,
    task_start: str,  # YYYY-MM-DD
    task_end: str,    # YYYY-MM-DD
    task_state: str,
    task_color: int,
    task_target: str,
    user_email: str,
    table_name: str = "task_table",
):
    cursor.execute(
        f"""
        INSERT INTO {table_name}
            (team_name, task_name, task_start, task_end,
             task_state, task_color, task_target, user_email)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            team_name,
            task_name,
            task_start,
            task_end,
            task_state,
            task_color,
            task_target,
            user_email,
        ),
    )
    connection.commit()


    """
    팀 업무 + 개인 업무 한 번에 조회
    hide_done=True ⇒ DONE 상태 제외
    """

def load_task_from_db(
    *,
    cursor,
    team_name: str,
    task_target: str,
    user_email: str,
    hide_done: bool = True,
    table_name: str = "task_table",
) -> List[Dict[str, Any]]:
    sql = f"""
        SELECT * FROM {table_name}
        WHERE (team_name=%s OR (task_target=%s AND user_email=%s))
    """
    if hide_done:
        sql += " AND task_state <> 'DONE'"
    cursor.execute(sql, (team_name, task_target, user_email))
    return cursor.fetchall()


def delete_task_from_db(
    *,
    connection,
    cursor,
    team_name: str | None = None,
    task_name: str | None = None,
    user_email: str | None = None,
    table_name: str = "task_table",
) -> None:
    """  
      팀 단위 삭제 → team_name+task_name 전달  
      개인 할 일 삭제 → user_email+task_name 전달
    """
    if team_name:
        cursor.execute(
            f"DELETE FROM {table_name} WHERE team_name=%s AND task_name=%s",
            (team_name, task_name),
        )
    else:
        cursor.execute(
            f"DELETE FROM {table_name} WHERE user_email=%s AND task_name=%s",
            (user_email, task_name),
        )


# ────────────────────────────────
#  Task UPDATE (state / color)
# ────────────────────────────────
def update_task_to_db(
    *,
    connection,
    cursor,
    team_name: str,
    task_name: str,
    task_state: str | None = None,
    task_color: int  | None = None,
    table_name: str = "task_table",
) -> None:
    """
    task_state·task_color 둘 중 전달된 항목만 UPDATE.
    팀 할 일은 team_name 으로, 개인 할 일은 team_name='' 로 호출.
    """
    sets: list[str] = []
    params: list[Any] = []
    if task_state is not None:
        sets.append("task_state=%s")
        params.append(task_state)
    if task_color is not None:
        sets.append("task_color=%s")
        params.append(task_color)
    if not sets:
        return  # 변경할 값 없음
    params.extend([team_name, task_name])
    sql = f"UPDATE {table_name} SET {', '.join(sets)} WHERE team_name=%s AND task_name=%s"
    cursor.execute(sql, params)
    connection.commit()
# ────────────────────────────────
# 4.  Board (Kanban)
# ────────────────────────────────


def add_board_to_db(
    *,
    connection,
    cursor,
    team_name: str,
    board_name: str,
    card_name: str,
    card_content: str,
    board_color: int,
    table_name: str = "board_table",
):
    cursor.execute(
        f"""
        INSERT INTO {table_name}
            (team_name, board_name, card_name, card_content, board_color)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (team_name, board_name, card_name, card_content, board_color),
    )
    connection.commit()


def load_board_from_db(
    *,
    cursor,
    team_name: str,
    board_name: str,
    table_name: str = "board_table",
) -> List[Dict[str, Any]]:
    cursor.execute(
        f"SELECT * FROM {table_name} WHERE team_name=%s AND board_name=%s",
        (team_name, board_name),
    )
    return cursor.fetchall()


def delete_board_from_db(
    *,
    connection,
    cursor,
    team_name: str,
    board_name: str,
    table_name: str = "board_table",
):
    cursor.execute(
        f"DELETE FROM {table_name} WHERE team_name=%s AND board_name=%s",
        (team_name, board_name),
    )
    connection.commit()

def update_board_to_db(
    *,
    connection,
    cursor,
    team_name: str,
    board_name: str,
    board_color: int,
    table_name: str = "board_table",
) -> None:
    """
    칸반 컬럼(board)의 색상만 변경.
    """
    cursor.execute(
        f"UPDATE {table_name} SET board_color=%s WHERE team_name=%s AND board_name=%s",
        (board_color, team_name, board_name),
    )
    connection.commit()


def delete_card_from_db(
    *,
    connection,
    cursor,
    team_name: str,
    board_name: str,
    card_name: str,
    table_name: str = "board_table",
):
    cursor.execute(
        f"""
        DELETE FROM {table_name}
         WHERE team_name=%s AND board_name=%s AND card_name=%s
        """,
        (team_name, board_name, card_name),
    )
    connection.commit()


# ────────────────────────────────
# 5.  Member
# ────────────────────────────────


def _owner_to_int(val: bool | int) -> int:
    return int(bool(val))


def add_member_to_db(
    *,
    connection,
    cursor,
    team_name: str,
    user_email: str,
    is_owner: bool = False,
    table_name: str = "member_table",
):
    cursor.execute(
        f"""
        INSERT INTO {table_name} (team_name, user_email, user_owner)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE user_owner = VALUES(user_owner)
        """,
        (team_name, user_email, _owner_to_int(is_owner)),
    )
    connection.commit()


def load_member_from_db(
    *,
    cursor,
    team_name: str | None = None,
    user_email: str | None = None,
    table_name: str = "member_table",
) -> List[Dict[str, Any]]:
    if team_name and not user_email:
        cursor.execute(
            f"SELECT * FROM {table_name} WHERE team_name=%s", (team_name,)
        )
    elif user_email and not team_name:
        cursor.execute(
            f"SELECT * FROM {table_name} WHERE user_email=%s", (user_email,)
        )
    elif team_name and user_email:
        cursor.execute(
            f"""SELECT * FROM {table_name}
                 WHERE team_name=%s AND user_email=%s""",
            (team_name, user_email),
        )
    else:
        cursor.execute(f"SELECT * FROM {table_name}")
    return cursor.fetchall()


def update_member_to_db(
    *,
    connection,
    cursor,
    team_name: str,
    user_email: str,
    is_owner: bool,
    table_name: str = "member_table",
):
    cursor.execute(
        f"""
        UPDATE {table_name}
           SET user_owner=%s
         WHERE team_name=%s AND user_email=%s
        """,
        (_owner_to_int(is_owner), team_name, user_email),
    )
    connection.commit()


def delete_member_from_db(
    *,
    connection,
    cursor,
    team_name: str,
    user_email: str,
    table_name: str = "member_table",
):
    cursor.execute(
        f"DELETE FROM {table_name} WHERE team_name=%s AND user_email=%s",
        (team_name, user_email),
    )
    connection.commit()


def delete_team_from_db(
    *,
    connection,
    cursor,
    team_name: str,
    member_table: str = "member_table",
    task_table: str = "task_table",
    board_table: str = "board_table",
):
    cursor.execute(f"DELETE FROM {member_table} WHERE team_name=%s", (team_name,))
    cursor.execute(f"DELETE FROM {task_table} WHERE team_name=%s", (team_name,))
    cursor.execute(f"DELETE FROM {board_table} WHERE team_name=%s", (team_name,))
    connection.commit()


# ────────────────────────────────
# 6.  public export list
# ────────────────────────────────

__all__ = [
    # connection
    "init_db","close_db",
    # setting
    "load_setting_from_db",
    # user
    "add_user_to_db","load_user_from_db","delete_user_from_db",
    # task
    "add_task_to_db","load_task_from_db","delete_task_from_db",
    # board
    "add_board_to_db","load_board_from_db","delete_board_from_db","delete_card_from_db",
    # member
    "add_member_to_db","load_member_from_db","update_member_to_db",
    "delete_member_from_db","delete_team_from_db",
    #update_task_to_db(...), update_board_to_db(...) 추가
    "update_task_to_db","update_board_to_db",
]
