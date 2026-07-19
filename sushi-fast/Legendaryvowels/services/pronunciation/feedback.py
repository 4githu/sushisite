from ..rules import PRONUNCIATION_EVALUATION_RULES


class FormantFeedbackGenerator:
    def generate(
        self,
        score: float,
        delta: dict[str, float],
    ) -> str:
        rules = PRONUNCIATION_EVALUATION_RULES
        if score >= rules.good_score_threshold:
            return "정답 LPC 곡선과 전반적으로 유사합니다. 현재 발음을 유지하세요."

        scales = {
            "F1": rules.f1_scale_hz,
            "F2": rules.f2_scale_hz,
            "F3": rules.f3_scale_hz,
        }
        if not delta:
            return "정답 LPC 곡선과 비교했지만 포먼트 차이를 충분히 특정하지 못했습니다."

        dominant = max(delta, key=lambda name: abs(delta[name]) / scales[name])
        difference = delta[dominant]

        if dominant == "F1":
            return (
                "F1을 조금 더 낮추세요. 혀 높이를 높이는 방향을 시도해 보세요."
                if difference > 0
                else "F1을 조금 더 높이세요. 혀 높이를 낮추는 방향을 시도해 보세요."
            )
        if dominant == "F2":
            return (
                "F2를 조금 더 낮추세요. 혀 위치를 뒤쪽으로 조정해 보세요."
                if difference > 0
                else "F2를 조금 더 높이세요. 혀 위치를 앞쪽으로 조정해 보세요."
            )
        return (
            "F3를 조금 더 낮추세요. 정답 곡선의 세 번째 봉우리를 확인하세요."
            if difference > 0
            else "F3를 조금 더 높이세요. 정답 곡선의 세 번째 봉우리를 확인하세요."
        )
