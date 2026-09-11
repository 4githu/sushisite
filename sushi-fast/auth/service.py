from . import userdb
from . import sushihash
from . import email_verified
import time


def login_with_password(email, password):
    user = userdb.get_user(email)
    if not user:
        return False, "이메일 또는 비밀번호가 올바르지 않습니다."

    try:
        if sushihash.check_hash(password, user['password_hash']):
            return True, user
    except sushihash.PasswordTooLongError:
        return False, "비밀번호가 너무 깁니다. 비밀번호를 재설정해주세요."

    return False, "이메일 또는 비밀번호가 올바르지 않습니다."


def request_password_reset(email):
    """Send a one-hour code only when an account exists; do not reveal account existence."""
    user = userdb.get_user(email)
    if not user:
        return True

    code = email_verified.send_verification_email(email, user["name"])
    userdb.save_password_reset_code(email, str(code), int(time.time()))
    return True


def reset_password(email, code, new_password):
    reset = userdb.get_password_reset_code(email)
    if not reset or str(reset["code"]) != str(code):
        return False, "유효하지 않은 인증 코드입니다."

    if int(time.time()) - reset["created_at"] > 3600:
        userdb.delete_password_reset_code(email)
        return False, "인증 코드가 만료되었습니다. 다시 요청해주세요."

    user = userdb.get_user(email)
    if not user:
        userdb.delete_password_reset_code(email)
        return False, "비밀번호를 재설정할 계정을 찾을 수 없습니다."

    try:
        password_hash = sushihash.make_hash(new_password)
    except sushihash.PasswordTooLongError as error:
        return False, str(error)

    userdb.update_password(user["id"], password_hash)
    userdb.delete_password_reset_code(email)
    return True, None

def send_verification_email(email, password = None, name = None):
    if userdb.get_imsi_user(email):
        userdb.delete_imsi_user(email)
    
    user = userdb.get_user(email)
    if user:
        code = email_verified.send_verification_email(email, user['name'])
        userdb.make_imsi_user(email, None, None, int(time.time()), code)
        return True
    elif password and name:
        code = email_verified.send_verification_email(email, name)
        userdb.make_imsi_user(email, sushihash.make_hash(password), name, int(time.time()), code)
        return True 
    return False

def verify_login_code(email, code):
    user = userdb.get_imsi_user(email)
    if user and user['email_code'] == code:
        if int(time.time()) - user['created_at'] > 3600:  # 1시간(3600초) 이상 경과한 경우
            userdb.delete_imsi_user(user['id'])
            return False, "인증 코드가 만료되었습니다. 다시 시도해주세요."
        user = userdb.get_user(email)
        userdb.delete_imsi_user(user['id'])
        return True, user
    return False, "유효하지 않은 인증 코드입니다."

def verify_register_code(email, code, email_verified=0):
    user = userdb.get_imsi_user(email)
    if user and user['email_code'] == code:
        if int(time.time()) - user['created_at'] > 3600:  # 1시간(3600초) 이상 경과한 경우
            userdb.delete_imsi_user(user['id'])
            return False, "인증 코드가 만료되었습니다. 다시 시도해주세요."
        userdb.create_user(user['email'], user['password_hash'], user['name'], user['created_at'], email_verified=email_verified)
        userdb.delete_imsi_user(user['id'])
        return True, user
    return False, "유효하지 않은 인증 코드입니다."

def edit_user(id=None, password=None, email=None, new_password=None, name=None):
    user = userdb.get_user(user_id=id)

    if user is None:
        return False, "없는 유저입니다."

    if email is None or email.strip() == "":
        email = user["email"]

    if name is None or name.strip() == "":
        name = user["name"]

    if new_password is None or new_password.strip() == "":
        password_hash = user["password_hash"]
    else:
        try:
            password_matches = password is not None and sushihash.check_hash(password, user["password_hash"])
        except sushihash.PasswordTooLongError:
            password_matches = False
        if not password_matches:
            return False, "현재 비밀번호가 올바르지 않습니다."
        try:
            password_hash = sushihash.make_hash(new_password)
        except sushihash.PasswordTooLongError as error:
            return False, str(error)

    userdb.edit_user(id, email, password_hash, name)

    return True, userdb.get_user(user_id=id)

def delete_user(id):
    userdb.delete_user(id)

def main():
    
    email = input("이메일을 입력하세요: ")
    password1 = input("비밀번호를 입력하세요: ")
    name = input("이름을 입력하세요: ")
    send_verification_email(email, password1, name)
    code = input("인증 이메일이 전송되었습니다. 이메일을 확인하고 인증 코드를 입력하세요.")
    verify_result = verify_register_code(email, code)
    if verify_result[0]:
        print(f"회원가입 성공! 환영합니다, {verify_result[1]['name']}님.")
    else:
        print(f"회원가입 실패! {verify_result[1]}")
    print("로그인 시도:")
    password2 = input("비밀번호를 입력하세요: ")
    user = login_with_password(email, password2)
    if user:
        print(f"로그인 성공! 환영합니다, {user['name']}님.")
        id = user['id']
    else:
        print("로그인 실패! 이메일 또는 비밀번호가 올바르지 않습니다.")
    
    paassword3 = input("회원 정보 변경 전 기존 비밀번호를 입력하세요: ")
    new_name = input("이름을 변경하려면 새 이름을 입력하세요: ")
    new_user = edit_user(id=id, password=paassword3, name=new_name)
    print(f"이름 변경 완료! 새 이름: {new_user['name']}")
    delete_user(user['id'])
    print(f"회원 삭제 확인 : {userdb.get_user(user['id'])}")

if __name__ == "__main__":
    main()
