"""Parent payment acknowledgement, separate from assistant payout records."""
from contextlib import closing
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, ConfigDict
from .settlement_requests import SettlementRequestError


class ParentPaymentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    studentKey: str = Field(min_length=1, max_length=300)
    paid: bool


class ManualDeliveryConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    studentKey: str = Field(min_length=1, max_length=300)


class ParentSettlements:
    def __init__(self, service):
        self.service = service
        with closing(service._connect()) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS aura_parent_settlement_status(
                user_id INTEGER NOT NULL, year INTEGER NOT NULL, month INTEGER NOT NULL,
                recipient_hash TEXT NOT NULL, paid INTEGER NOT NULL, amount INTEGER NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(user_id,year,month,recipient_hash))""")
            conn.execute("""CREATE TABLE IF NOT EXISTS aura_parent_settlement_delivery_confirmations(
                user_id INTEGER NOT NULL, year INTEGER NOT NULL, month INTEGER NOT NULL,
                snapshot_id INTEGER NOT NULL, recipient_hash TEXT NOT NULL,
                confirmed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(user_id,year,month,snapshot_id,recipient_hash))""")

    def _snapshot_messages(self, owner, year, month):
        with closing(self.service._connect()) as conn:
            row = conn.execute("SELECT id FROM aura_settlement_snapshots WHERE user_id=? AND year=? AND month=? AND pricing_version>=6",
                               (owner, year, month)).fetchone()
        if not row:
            return None, []
        _, payload, _ = self.service._snapshot(owner, row["id"])
        return row["id"], self.service._messages(payload, "김지후")[0]

    def _messages(self, owner, year, month):
        return self._snapshot_messages(owner, year, month)[1]

    def list(self, owner, year, month):
        snapshot_id, messages = self._snapshot_messages(owner, year, month)
        with closing(self.service._connect()) as conn:
            states = {row["recipient_hash"]: row for row in conn.execute(
                "SELECT * FROM aura_parent_settlement_status WHERE user_id=? AND year=? AND month=?", (owner, year, month))}
            confirmations = {}
            if snapshot_id is not None:
                confirmations = {row["recipient_hash"]: row for row in conn.execute(
                    "SELECT recipient_hash,confirmed_at FROM aura_parent_settlement_delivery_confirmations "
                    "WHERE user_id=? AND year=? AND month=? AND snapshot_id=?",
                    (owner, year, month, snapshot_id))}
        result = []
        for message in messages:
            state = states.get(self.service._digest(message["studentKey"]))
            confirmation = confirmations.get(self.service._digest(message["studentKey"]))
            amount = message["parentCharge"]
            status = "pending"
            if state and state["paid"]:
                status = "paid" if state["amount"] == amount else "needs_review"
            result.append({"studentKey": message["studentKey"], "status": status, "amount": amount,
                           "paidAmount": state["amount"] if state and state["paid"] else 0,
                           "updatedAt": state["updated_at"] if state else None,
                           "manualDeliveryConfirmed": bool(confirmation),
                           "manualDeliveryConfirmedAt": confirmation["confirmed_at"] if confirmation else None})
        return {"items": result}

    def update(self, owner, year, month, student_key, paid):
        # Derive the amount and identity from this owner's current server snapshot.
        message = next((m for m in self._messages(owner, year, month) if m["studentKey"] == student_key), None)
        if message is None:
            raise SettlementRequestError(404, "recipient_not_billable", "선택한 학생은 이 월의 학부모 청구 대상이 아닙니다.")
        with closing(self.service._connect()) as conn:
            conn.execute("""INSERT INTO aura_parent_settlement_status(user_id,year,month,recipient_hash,paid,amount)
                VALUES(?,?,?,?,?,?) ON CONFLICT(user_id,year,month,recipient_hash)
                DO UPDATE SET paid=excluded.paid,amount=excluded.amount,updated_at=CURRENT_TIMESTAMP""",
                (owner, year, month, self.service._digest(student_key), int(paid), message["parentCharge"]))
        return next(item for item in self.list(owner, year, month)["items"] if item["studentKey"] == student_key)

    def confirm_delivery(self, owner, year, month, student_key):
        snapshot_id, messages = self._snapshot_messages(owner, year, month)
        message = next((item for item in messages if item["studentKey"] == student_key), None)
        if message is None or snapshot_id is None:
            raise SettlementRequestError(404, "recipient_not_billable", "선택한 학생은 이 월의 학부모 청구 대상이 아닙니다.")
        recipient_hash = self.service._digest(student_key)
        with closing(self.service._connect()) as conn:
            conn.execute("""INSERT INTO aura_parent_settlement_delivery_confirmations
                (user_id,year,month,snapshot_id,recipient_hash)
                VALUES(?,?,?,?,?) ON CONFLICT(user_id,year,month,snapshot_id,recipient_hash) DO NOTHING""",
                (owner, year, month, snapshot_id, recipient_hash))
        return next(item for item in self.list(owner, year, month)["items"] if item["studentKey"] == student_key)


def build_router(ledger, owner_dependency, read_owner_dependency):
    router = APIRouter(prefix="/aura/settlements/parents", tags=["aura-parent-settlements"])

    @router.get("")
    def get_status(response: Response, year: int = Query(ge=2000, le=2100), month: int = Query(ge=1, le=12), owner: int = Depends(read_owner_dependency)):
        response.headers["Cache-Control"] = "no-store"
        return ledger.list(owner, year, month)

    @router.patch("")
    def update_status(data: ParentPaymentUpdate, owner: int = Depends(owner_dependency)):
        try:
            return ledger.update(owner, data.year, data.month, data.studentKey, data.paid)
        except SettlementRequestError as error:
            raise HTTPException(error.status_code, detail={"code": error.code, "message": error.message}) from error

    @router.patch("/delivery")
    def confirm_delivery(data: ManualDeliveryConfirmation, owner: int = Depends(owner_dependency)):
        try:
            return ledger.confirm_delivery(owner, data.year, data.month, data.studentKey)
        except SettlementRequestError as error:
            raise HTTPException(error.status_code, detail={"code": error.code, "message": error.message}) from error

    return router
