# %%
# .py3127_env\Scripts\activate
# pip install uvicorn fastapi python-multipart faster-whisper tensorflow-cpu
from uvicorn                        import run
from fastapi                        import FastAPI
from pydantic                       import BaseModel
from rds                            import (init_db,                    load_user_from_db,          load_task_from_db,          load_board_from_db,         load_member_from_db,
                                            close_db,                   add_user_to_db,             add_task_to_db,             add_board_to_db,            add_member_to_db,
                                            load_setting_from_db,       delete_user_from_db,        delete_task_from_db,        delete_board_from_db,       delete_team_from_db,
                                                                                                                                delete_card_from_db,        delete_member_from_db,
                                                                                                                                                            update_member_to_db)

# - - - 임시 선언하기 - - - #
KAKAO                       = None
GOOGLE                      = None
connection                  = None
cursor                      = None
app                         = FastAPI()

# - - - UserManagementRequest 선언하기 - - - #
class UserManagementRequest(BaseModel):
    user_email:         str
    user_nickname:      str
    user_image:         str

# - - - TaskManagementRequest 선언하기 - - - #
class TaskManagementRequest(BaseModel):
    team_name:          str # 팀, 할 일 소유 조건 1 (1/1)
    task_name:          str
    task_start:         str
    task_end:           str
    task_state:         str
    task_target:        str # 개인, 할 일 소유 조건 1 (1/2)
    user_email:         str # 개인, 할 일 소유 조건 2 (2/2)

# - - - BoardManagementRequest 선언하기 - - - #
class BoardManagementRequest(BaseModel):
    team_name:          str
    board_name:         str
    card_name:          str
    card_content:       str
    card_state:         str

# - - - MemberManagementRequest 선언하기 - - - #
class MemberManagementRequest(BaseModel):
    team_name:      str
    user_email:     str
    user_owner:     str

# - - - startup 구축하기 - - - #
@app.on_event("startup")
async def startup_event():
    global KAKAO, GOOGLE, connection, cursor
    
    connection, cursor = init_db()
    
    KAKAO, GOOGLE = load_setting_from_db(cursor         = cursor,
                                         table_name     = "setting_table")

# - - - /load_setting 구축하기 - - - #
@app.post("/load_setting")
async def load_setting():
    return {"kakao": KAKAO, "google": GOOGLE}

# - - - /load_user 구축하기 - - - #
@app.post("/load_user")
async def load_user(request: UserManagementRequest):
    USER = load_user_from_db(cursor         = cursor,
                             user_email     = request.user_email,
                             table_name     = "user_table")
    
    return {"user": USER}

# - - - /load_task 구축하기 - - - #
@app.post("/load_task")
async def load_task(request: TaskManagementRequest):
    TASK = load_task_from_db(cursor             = cursor,
                             team_name          = request.team_name,        # 팀, 할 일 소유 조건 1 (1/1)
                             task_target        = request.task_target,      # 개인, 할 일 소유 조건 1 (1/2)
                             user_email         = request.user_email,       # 개인, 할 일 소유 조건 2 (2/2)
                             table_name         = "task_table")
    
    return {"task": TASK}

# - - - /load_board 구축하기 - - - #
@app.post("/load_board")
async def load_board(request: BoardManagementRequest):
    BOARD = load_board_from_db(cursor           = cursor,
                               team_name        = request.team_name,
                               board_name       = request.board_name,
                               table_name       = "board_table")
    
    return {"board": BOARD}

# - - - /load_member 구축하기 - - - #
@app.post("/load_member")
async def load_member(request: MemberManagementRequest):
    MEMBER = load_member_from_db(cursor         = cursor,
                                 team_name      = request.team_name,
                                 table_name     = "member_table")
    
    return {"member": MEMBER}

# - - - /add_user 구축하기 - - - #
@app.post("/add_user")
async def add_user(request: UserManagementRequest):
    add_user_to_db(connection           = connection,
                   cursor               = cursor,
                   user_email           = request.user_email,
                   user_nickname        = request.user_nickname,
                   user_image           = request.user_image,
                   table_name           = "user_table")

# - - - /add_task 구축하기 - - - #
@app.post("/add_task")
async def add_task(request: TaskManagementRequest):
    add_task_to_db(connection       = connection,
                   cursor           = cursor,
                   team_name        = request.team_name,
                   task_name        = request.task_name,
                   task_start       = request.task_start,
                   task_end         = request.task_end,
                   task_state       = request.task_state,
                   task_target      = request.task_target,
                   user_email       = request.user_email,
                   table_name       = "task_table")

# - - - /add_board 구축하기 - - - #
@app.post("/add_board")
async def add_board(request: BoardManagementRequest):
    add_board_to_db(connection          = connection,
                    cursor              = cursor,
                    team_name           = request.team_name,
                    board_name          = request.board_name,
                    card_name           = request.card_name,
                    card_content        = request.card_content,
                    card_state          = request.card_state,
                    table_name          = "board_table")

# - - - /add_member 구축하기 - - - #
@app.post("/add_member")
async def add_member(request: MemberManagementRequest):
    add_member_to_db(connection     = connection,
                     cursor         = cursor,
                     team_name      = request.team_name,
                     user_email     = request.user_email,
                     user_owner     = request.user_owner,
                     table_name     = "member_table")

# - - - /delete_user 구축하기 - - - #
@app.post("/delete_user")
async def delete_user(request: UserManagementRequest):
    delete_user_from_db(connection          = connection,
                        cursor              = cursor,
                        user_email          = request.user_email,
                        table_name_1        = "user_table",             # 탈퇴하기로서 데이터를 삭제할 때,
                        table_name_2        = "task_table",             # 만약 task_target != ''이면 삭제 안 함 (팀 데이터 보존, 직접 터치하여 user_email = task_target으로 삭제)
                        table_name_3        = "member_table")           # 만약 user_owner == 'true'이면 자동 팀장 인계

# - - - /delete_task 구축하기 - - - #
@app.post("/delete_task")
async def delete_task(request: TaskManagementRequest):
    delete_task_from_db(connection      = connection,
                        cursor          = cursor,
                        team_name       = request.team_name,        # 팀 단위 할 일을 삭제할 때.
                        task_name       = request.task_name,
                        user_email      = request.user_email,       # 개인 단위 할 일을 삭제할 때.
                        table_name      = "task_table")

# - - - /delete_board 구축하기 - - - #
@app.post("/delete_board")
async def delete_board(request: BoardManagementRequest):
    delete_board_from_db(connection     = connection,
                         cursor         = cursor,
                         team_name      = request.team_name,
                         board_name     = request.board_name,
                         table_name     = "board_table")

# - - - /delete_card 구축하기 - - - #
@app.post("/delete_card")
async def delete_card(request: BoardManagementRequest):
    delete_card_from_db(connection      = connection,
                        cursor          = cursor,
                        team_name       = request.team_name,
                        board_name      = request.board_name,
                        card_name       = request.card_name,
                        table_name      = "board_table")

# - - - /delete_team 구축하기 - - - #
@app.post("/delete_team")
async def delete_team(request: MemberManagementRequest):
    delete_team_from_db(connection          = connection,
                        cursor              = cursor,
                        team_name           = request.team_name,
                        table_name_1        = "task_table",
                        table_name_2        = "board_table",
                        table_name_3        = "member_table")

# - - - /delete_member 구축하기 - - - #
@app.post("/delete_member")
async def delete_member(request: MemberManagementRequest):
    delete_member_from_db(connection        = connection,
                          cursor            = cursor,
                          user_email        = request.user_email,
                          table_name        = "member_table")

# - - - /update_member 구축하기 - - - #
@app.post("/update_member")
async def update_member(request: MemberManagementRequest):
    update_member_to_db(connection     = connection,
                        cursor         = cursor,
                        user_owner     = request.user_owner,
                        table_name     = "member_table")

# - - - shutdown 구축하기 - - - #
@app.on_event("shutdown")
async def shutdown_event():
    close_db(connection     = connection,
             cursor         = cursor)

# - - - server 실행하기 - - - #
if __name__ == "__main__":
    run(              "server:app",
        host        = "0.0.0.0",
        port        = 8000,
        reload      = False)

# %%
