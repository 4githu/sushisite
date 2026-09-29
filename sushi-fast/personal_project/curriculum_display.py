"""Presentation text only. The versioned rule/source data is never rewritten."""
import html
import re

LABELS = {
 'required.all':'필수 과목 목록', 'required_credits':'전공필수 학점', 'major_double_credits':'복수전공 학점',
 'minor_credits':'부전공 학점', 'major_min_credits':'전공 최소 학점', 'major_required_known':'확인된 필수 과목',
 'major_required_match':'전공필수 분류', 'major_select_match':'전공선택 분류', 'select_min':'전공선택 최소 학점',
 'recog_max':'타 전공 인정 상한', 'english_min_courses':'외국어 강의 최소 과목 수',
 'BASELINE-ASSUMED':'임시 기준', 'baseline':'임시 기준', 'spec':'자료', 'by track':'유형별',
 'required':'필수 조건', 'single':'단일전공', 'multi':'다전공 병행', 'double':'복수전공', 'minor':'부전공',
 'math':'수학', 'science':'과학', 'general':'교양', 'msc':'수학·과학·컴퓨팅', 'suri':'수학·과학·컴퓨팅',
}
GENERAL = {'hum':'인문대학','natsci':'자연과학대학','soc':'사회과학대학','biz':'경영대학','music':'음악대학','art':'미술대학','agri_sci':'농업생명과학대학','edu_hum':'사범대학 인문계열','edu_natsci':'사범대학 자연계열'}

def text(value):
    value=html.unescape(html.unescape(value)).replace('\xa0',' ')
    if re.search(r'HTTP 200이나|GNUBOARD',value):
        return '학과의 공식 이수규정을 확인하지 못해 농업생명과학대학 공통 기준을 임시 적용했습니다. 교양 학점 등 일부 수치는 자료끼리 일치하지 않으며, 필수 과목코드도 확인되지 않았습니다. 정확한 기준은 학과 사무실에서 확인해주세요.'
    if 'colleges 모드' in value:
        value=value.split('출처 ')[0].rstrip()
    value=re.sub(r'\([^)]*(?:HTTP[S]? |인증서|-k는|Elementor|og:description)[^)]*\)','(공식 자료 확인이 필요합니다)',value)
    value=re.sub(r'\b(?:[\w/]+/)?[\w-]+\.md\b','원본 자료',value)
    value=re.sub(r'\b([a-z_]+)_(202[0-9])\b',lambda m:f"{GENERAL.get(m[1],'해당 단과대학')} 교양 기준({m[2]}년)",value)
    for old,new in sorted(LABELS.items(),key=lambda pair:-len(pair[0])):
        value=re.sub(r'(?<![A-Za-z_])'+re.escape(old)+r'(?![A-Za-z_])',new,value)
    value=value.replace('SPA-blocked','공식 페이지 확인 불가').replace('standard','공통 기준').replace('어댑터','적용').replace('미모델링','세부 조건 미반영')
    value=re.sub(r'⚠ FIX\(([^)]+)\):',r'수정 안내(\1):',value)
    value=value.replace('→ 필수 과목 목록 생략','→ 필수 과목 목록 미제공')
    return value

def present(value, key=''):
    if isinstance(value,dict):return {k:present(v,k) for k,v in value.items()}
    if isinstance(value,list):return [present(v,key) for v in value]
    if isinstance(value,str) and key not in ('code','codes','code_prefixes','id','key','batch'):
        return text(value)
    return value

def source_links(source):
    return list(dict.fromkeys(url.rstrip('.,;)') for url in re.findall(r'https?://[^\s<>"\]]+',source)))
