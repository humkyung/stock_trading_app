# test_trader.py
from modules.trader import KisTrader

print("--- 한국투자증권 API 테스트 ---")

# 1. 객체 생성 및 로그인(토큰발급)
bot = KisTrader()

if bot.access_token:
    # 2. 잔고 조회 테스트
    print("\n[잔고 조회]")
    balance = bot.get_balance()
    if balance:
        for stock in balance:
            print(
                f"종목: {stock['prdt_name']}, 수량: {stock['hldg_qty']}, 수익률: {stock['evlu_pfls_rt']}%"
            )
    else:
        print("보유 종목이 없거나 조회 실패")

    # 3. (주의) 매수 주문 테스트 - 모의투자일 경우만 주석 해제하세요
    print("\n[매수 테스트]")
    bot.send_order("005930", 1, 0, "buy")  # 삼성전자 1주 시장가 매수
else:
    print("API 연결 실패. .env 파일을 확인하세요.")
