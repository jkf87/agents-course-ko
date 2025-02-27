from smolagents import CodeAgent, ToolCallingAgent, DuckDuckGoSearchTool, HfApiModel, tools
import json
from datetime import datetime
import gradio as gr
import os

def create_search_agent():
    # 웹 검색을 수행하는 에이전트
    return ToolCallingAgent(
        tools=[DuckDuckGoSearchTool()],
        model=HfApiModel()
    )

def create_writer_agent():
    # 파일 작성을 수행하는 에이전트
    return CodeAgent(
        tools=[],  # CodeAgent는 기본적으로 파일 시스템 작업이 가능합니다
        model=HfApiModel()
    )

def create_analyzer_agent():
    # 검색 결과를 분석하고 정리하는 에이전트
    return ToolCallingAgent(
        tools=[],  # 분석 에이전트는 특별한 도구가 필요하지 않으므로 빈 리스트 사용
        model=HfApiModel()
    )

def expand_query(agent, original_query, progress_logs=None):
    # 원본 쿼리를 여러 개의 세부 쿼리로 확장
    expansion_prompt = f"""
    다음 검색어와 관련된 4개의 구체적인 검색 쿼리를 생성해주세요.
    각각의 쿼리는 서로 다른 측면이나 관점을 다뤄야 하며, 실제 검색에 효과적인 형태여야 합니다.
    
    검색어: {original_query}
    
    응답 형식:
    1. JSON 형식으로 응답해주세요.
    2. 각 쿼리는 검색 엔진에서 좋은 결과를 얻을 수 있도록 구체적이어야 합니다.
    3. 쿼리는 한글로 작성해주세요.
    
    다음 형식으로 응답해주세요:
    {{
        "queries": [
            "구체적인 첫 번째 검색어",
            "구체적인 두 번째 검색어",
            "구체적인 세 번째 검색어",
            "구체적인 네 번째 검색어"
        ]
    }}
    """
    
    if progress_logs is not None:
        progress_logs.append("\n==== 쿼리 확장 프로세스 ====")
        progress_logs.append(f"[확장 요청 프롬프트]\n{expansion_prompt}")
    
    try:
        # 에이전트 응답 받기
        if progress_logs is not None:
            progress_logs.append("\n[에이전트에게 쿼리 확장 요청 중...]")
        
        result = agent.run(expansion_prompt)
        
        if progress_logs is not None:
            progress_logs.append(f"\n[에이전트 응답 - RAW]\n{result}")
            progress_logs.append("\n[JSON 파싱 시도 중...]")
        
        parsed_result = json.loads(result)
        
        if "queries" not in parsed_result or not parsed_result["queries"]:
            if progress_logs is not None:
                progress_logs.append("\n[오류] JSON에 'queries' 키가 없거나 비어 있습니다. 원본 쿼리 사용.")
            return [original_query]
        
        queries = parsed_result["queries"]
        if progress_logs is not None:
            progress_logs.append(f"\n[추출된 쿼리 - 필터링 전]\n{json.dumps(queries, ensure_ascii=False, indent=2)}")
        
        # 빈 쿼리나 너무 짧은 쿼리 필터링
        queries = [q for q in queries if q and len(q) > 2]
        
        if progress_logs is not None:
            progress_logs.append(f"\n[필터링 후 쿼리]\n{json.dumps(queries, ensure_ascii=False, indent=2)}")
        
        if not queries:
            if progress_logs is not None:
                progress_logs.append("\n[필터링 후 유효한 쿼리 없음] 원본 쿼리 사용.")
            return [original_query]
        
        return queries
        
    except Exception as e:
        if progress_logs is not None:
            progress_logs.append(f"\n[쿼리 확장 중 오류 발생] {str(e)}\n원본 쿼리를 사용합니다.")
        return [original_query]

def analyze_results(agent, search_results, progress_logs=None):
    # 검색 결과를 분석하고 유용한 정보만 추출
    analysis_prompt = f"""
    아래 제공된 검색 결과를 깊이 있게 분석하고 가장 중요하고 신뢰할 수 있는 정보를 추출해주세요.
    
    분석 시 다음 사항을 고려해주세요:
    1. 여러 소스에서 반복되는 정보는 신뢰성이 높을 가능성이 있습니다.
    2. 최신 정보를 우선적으로 고려하세요.
    3. 출처가 명확한 정보를 우선적으로 선택하세요.
    4. 각 발견사항은 명확하고 구체적인 내용을 담아야 합니다.
    5. 모호하거나 불확실한 정보는 제외하세요.
    
    검색 결과:
    {json.dumps(search_results, indent=2, ensure_ascii=False)[:100000]}  # 너무 길면 잘라서 사용
    
    다음 JSON 형식으로 응답해주세요:
    {{
        "key_findings": [
            {{
                "content": "첫 번째 발견사항의 상세 내용",
                "reliability": "높음/중간/낮음",
                "source": "발견된 출처 (알 수 있는 경우)"
            }},
            {{
                "content": "두 번째 발견사항의 상세 내용",
                "reliability": "높음/중간/낮음",
                "source": "발견된 출처 (알 수 있는 경우)"
            }},
            ...계속...
        ]
    }}
    """
    
    if progress_logs is not None:
        progress_logs.append("\n==== 검색 결과 분석 프로세스 ====")
        progress_logs.append("[분석 요청 프롬프트 - 헤더만 표시 (전체 길이가 너무 김)]\n" + analysis_prompt.split("검색 결과:")[0])
        progress_logs.append(f"\n[분석할 검색 결과 개수] {len(search_results)}개")
    
    try:
        # 검색 결과 분석 시도
        if progress_logs is not None:
            progress_logs.append("\n[에이전트에게 분석 요청 중...]")
        
        result = agent.run(analysis_prompt)
        
        if progress_logs is not None:
            progress_logs.append(f"\n[에이전트 분석 응답 - RAW]\n{result}")
            progress_logs.append("\n[JSON 파싱 시도 중...]")
        
        # JSON 파싱 시도
        try:
            parsed_result = json.loads(result)
            
            if progress_logs is not None:
                progress_logs.append(f"\n[JSON 파싱 성공]\n{json.dumps(parsed_result, ensure_ascii=False, indent=2)[:1000]}...")
            
            if "key_findings" in parsed_result and parsed_result["key_findings"]:
                # JSON 구조가 예상대로인 경우
                if progress_logs is not None:
                    progress_logs.append("\n[예상 JSON 구조 확인됨] 'key_findings' 키 있음")
                
                findings = []
                for item in parsed_result["key_findings"]:
                    if isinstance(item, dict) and "content" in item:
                        # 신뢰도 정보 추가
                        reliability = item.get("reliability", "")
                        source = item.get("source", "")
                        
                        content = item["content"]
                        if reliability and source:
                            findings.append(f"{content} (신뢰도: {reliability}, 출처: {source})")
                        elif reliability:
                            findings.append(f"{content} (신뢰도: {reliability})")
                        elif source:
                            findings.append(f"{content} (출처: {source})")
                        else:
                            findings.append(content)
                    elif isinstance(item, str) and item:
                        findings.append(item)
                
                if progress_logs is not None:
                    progress_logs.append(f"\n[처리된 발견사항] {len(findings)}개 항목 추출됨")
                
                if findings:
                    return findings
            elif "key_findings" in parsed_result and isinstance(parsed_result["key_findings"], list):
                # 단순 문자열 목록인 경우
                if progress_logs is not None:
                    progress_logs.append("\n[단순 목록 구조 확인됨] 문자열 목록 처리 중")
                
                findings = [item for item in parsed_result["key_findings"] if item and len(str(item)) > 10]
                
                if progress_logs is not None:
                    progress_logs.append(f"\n[필터링 후 발견사항] {len(findings)}개 항목 추출됨")
                
                if findings:
                    return findings
            else:
                if progress_logs is not None:
                    progress_logs.append("\n[예상과 다른 JSON 구조] 'key_findings' 키가 없거나 다른 형식")
        
        except json.JSONDecodeError:
            # JSON 파싱에 실패한 경우, 줄 단위로 의미 있는 정보 추출 시도
            if progress_logs is not None:
                progress_logs.append("\n[JSON 파싱 실패] 텍스트 분석으로 전환")
        
        # JSON 파싱이 실패하거나 예상 구조가 아닌 경우, 텍스트 분석 시도
        if progress_logs is not None:
            progress_logs.append("\n[텍스트 기반 분석 시작] 줄 단위 분석")
        
        lines = result.split("\n")
        findings = []
        for line in lines:
            line = line.strip()
            # 의미 있는 줄만 추출 (짧은 줄, JSON 표기, 빈 줄 제외)
            if line and len(line) > 30 and not (line.startswith('{') or line.startswith('}') or line.startswith('[') or line.startswith(']')):
                findings.append(line)
        
        if progress_logs is not None:
            progress_logs.append(f"\n[텍스트 분석 결과] {len(findings)}개 의미 있는 줄 추출됨")
        
        if findings:
            return findings
            
        # 모든 시도가 실패한 경우 기본 메시지 반환
        if progress_logs is not None:
            progress_logs.append("\n[분석 실패] 모든 분석 방법 실패. 기본 메시지 반환")
        
        return ["검색 결과에서 유의미한 정보를 추출하지 못했습니다. 다른 검색어로 시도해보세요."]
            
    except Exception as e:
        if progress_logs is not None:
            progress_logs.append(f"\n[분석 중 예외 발생] {str(e)}")
        
        return [f"검색 결과 분석 중 오류가 발생했습니다: {str(e)}"]

def generate_report(writer_agent, query, findings, expanded_queries, progress_logs=None):
    """
    에이전트를 사용하여 더 풍부한 보고서 생성
    """
    report_prompt = f"""
    다음 주제와 발견된 정보를 바탕으로 상세하고 종합적인 리서치 보고서를 작성해주세요:

    주제: {query}

    조사에 사용된 검색어:
    {expanded_queries}

    발견된 주요 정보:
    {chr(10).join([f"- {finding}" for finding in findings])}

    보고서는 다음 형식을 따라주세요:
    1. 제목: 주제를 잘 나타내는 명확한 제목 (굵은 글씨)
    2. 개요: 주제에 대한 소개와 조사의 배경 및 목적 (최소 200자 이상)
    3. 주요 발견사항: 가장 중요하고 관련성 높은 정보를 상세히 설명 (각 항목당 최소 200자 이상, 총 5개 이상의 항목)
    4. 세부 분석:
       a. 정보의 신뢰성 평가 (소스 분석, 교차 검증 결과)
       b. 발견된 쟁점이나 논란 (있는 경우)
       c. 시간적 변화나 추세 (관련이 있는 경우)
       d. 지역적/문화적 차이점 (관련이 있는 경우)
    5. 통합적 분석: 모든 발견사항들을 종합적으로 분석한 심층 해석 (최소 500자 이상)
    6. 결론 및 제언: 전체 내용의 요약과 향후 주목할 점 또는 권장사항 (최소 400자 이상)
    7. 이 보고서의 한계: 정보 수집 과정의 제한사항이나 향후 추가 연구가 필요한 부분
    
    보고서 작성 시 주의사항:
    - 각 섹션마다 충분한 내용과 깊이를 포함할 것 (전체 보고서는 최소 5000자 이상)
    - 단순 나열이 아닌 사실들을 연결하고 해석하는 통합적 분석을 제공할 것
    - 가능한 경우 출처와 날짜를 포함할 것
    - 전문 용어가 있다면 간략히 설명할 것
    - 객관적이고 균형 잡힌 관점에서 서술할 것
    """
    
    if progress_logs is not None:
        progress_logs.append("\n==== 보고서 생성 프로세스 ====")
        progress_logs.append("[보고서 작성 요청 프롬프트]\n" + report_prompt.split("발견된 주요 정보:")[0] + "발견된 주요 정보: [...]")
        progress_logs.append(f"\n[처리할 발견사항 수] {len(findings)}개")
    
    try:
        if progress_logs is not None:
            progress_logs.append("\n[에이전트에게 보고서 작성 요청 중...]")
        
        report_content = writer_agent.run(report_prompt)
        
        if progress_logs is not None:
            progress_logs.append(f"\n[에이전트 보고서 응답 - RAW]\n{report_content[:500]}...(이하 생략)")
            progress_logs.append(f"\n[보고서 길이] {len(report_content)} 자")
        
        # 현재 시간 추가
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        final_report = f"생성 시간: {now}\n\n{report_content}"
        
        if progress_logs is not None:
            progress_logs.append("\n[보고서 생성 완료]")
        
        return final_report
    except Exception as e:
        if progress_logs is not None:
            progress_logs.append(f"\n[보고서 생성 중 오류 발생] {str(e)}\n기본 보고서 생성으로 전환")
        
        # 에러 발생시 기본 보고서 생성
        return generate_simple_report(query, findings, progress_logs)

def generate_simple_report(query, findings, progress_logs=None):
    """
    기본적인 보고서 형식으로 생성 (에이전트 실패 시 대체용)
    """
    if progress_logs is not None:
        progress_logs.append("\n[기본 보고서 생성 시작]")
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report = f"""
=== AI 리서치 보고서: {query} ===
생성 시간: {now}

🔍 개요:
"{query}"에 대한 자동화된 웹 검색 결과를 바탕으로 작성된 리포트입니다.
이 보고서는 다양한 온라인 소스에서 수집된 정보를 종합하여 제공합니다.

📊 주요 발견사항:

"""
    for i, finding in enumerate(findings, 1):
        report += f"{i}. {finding}\n\n"
    
    report += """
💡 결론:
위 정보는 자동화된 검색을 통해 수집되었으며, 각 항목의 정확성과 최신성은 원본 출처에 따라 달라질 수 있습니다.
더 정확하고 상세한 정보를 위해서는 전문가의 검증이 권장됩니다.
"""
    
    if progress_logs is not None:
        progress_logs.append(f"\n[기본 보고서 생성 완료] 길이: {len(report)} 자")
    
    return report

def save_logs_to_file(logs, query, timestamp, search_results=None, expanded_queries=None, findings=None, report=None, agent_prompts=None):
    """로그를 파일로 저장하는 함수"""
    os.makedirs('logs', exist_ok=True)
    
    sanitized_query = "".join(c for c in query if c.isalnum() or c in ' -_').strip().replace(' ', '_')[:30]
    log_filename = f"log_{sanitized_query}_{timestamp}.txt"
    log_path = os.path.join('logs', log_filename)
    
    with open(log_path, 'w', encoding='utf-8') as f:
        # 헤더 정보
        f.write(f"=========================================================\n")
        f.write(f"===== 에이전트 시스템 전체 로그: {query} =====\n")
        f.write(f"=========================================================\n")
        f.write(f"시작 시간: {datetime.fromtimestamp(int(timestamp.split('_')[0])).strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # 상세 프로세스 로그 (모든 단계와 과정 포함)
        f.write("=========================================================\n")
        f.write("===== 전체 프로세스 로그 (모든 중간 단계 포함) =====\n")
        f.write("=========================================================\n\n")
        f.write("\n".join(logs))
        
        # 구분선
        f.write("\n\n")
        f.write("=========================================================\n")
        f.write("===== 최종 결과 요약 =====\n")
        f.write("=========================================================\n\n")
        
        # 1. 쿼리 확장 로그
        f.write("===== 1. 쿼리 확장 결과 =====\n")
        if expanded_queries:
            f.write(expanded_queries + "\n\n")
        
        # 2. 검색 결과 로그
        f.write("===== 2. 검색 결과 (RAW) =====\n")
        if search_results:
            for i, result in enumerate(search_results):
                f.write(f"\n--- 검색 {i+1}: \"{result['query']}\" ---\n")
                f.write(result['result'])
                f.write("\n" + "-" * 80 + "\n")
        
        # 3. 분석 결과 로그
        f.write("\n===== 3. 분석 결과 =====\n")
        if findings:
            f.write(findings + "\n\n")
        
        # 4. 최종 보고서
        f.write("===== 4. 최종 보고서 =====\n")
        if report:
            f.write(report + "\n\n")
    
    return log_path

def process_query(query):
    # 에이전트들 생성
    progress_logs = []  # 진행 상황과 모든 중간 과정을 저장할 리스트
    
    # 시작 로깅
    progress_logs.append(f"==================================================")
    progress_logs.append(f"===== 멀티 에이전트 리서치 시스템 프로세스 시작 =====")
    progress_logs.append(f"==================================================")
    progress_logs.append(f"시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    progress_logs.append(f"검색 쿼리: '{query}'")
    
    # 에이전트 생성 로깅
    progress_logs.append("\n[에이전트 생성 시작]")
    
    search_agent = create_search_agent()
    progress_logs.append("[검색 에이전트 생성 완료] DuckDuckGoSearchTool 사용")
    
    analyzer_agent = create_analyzer_agent()
    progress_logs.append("[분석 에이전트 생성 완료] 도구 없음")
    
    writer_agent = create_writer_agent()
    progress_logs.append("[작성 에이전트 생성 완료] CodeAgent 사용\n")
    
    # 시작 타임스탬프 생성 (파일명용)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 진행 상황 업데이트 및 UI 반환 함수
    def update_ui(message=None, expanded=None, findings=None, report=None, file=None, log_file=None):
        if message:
            progress_logs.append(message)
        
        return (
            "\n".join(progress_logs[-15:]),  # UI에는 최근 15개 메시지만 표시
            expanded if expanded is not None else "",
            findings if findings is not None else "",
            report if report is not None else "",
            file,
            log_file
        )
    
    # 1단계: 쿼리 확장
    yield update_ui("1️⃣ 검색 쿼리를 확장하는 중...")
    progress_logs.append(f"\n[원본 쿼리] {query}")
    
    # 쿼리 확장 과정에 로그 전달
    expanded_queries = expand_query(analyzer_agent, query, progress_logs)
    expanded_queries_text = "\n".join([f"{i+1}. {q}" for i, q in enumerate(expanded_queries)])
    
    yield update_ui(f"✅ 쿼리 확장 완료: {len(expanded_queries)}개의 검색어 생성됨", expanded_queries_text)
    for i, eq in enumerate(expanded_queries, 1):
        yield update_ui(f"   {i}. {eq}", expanded_queries_text)
    
    # 2단계: 확장된 쿼리로 검색 수행
    yield update_ui("\n2️⃣ 검색을 수행하는 중...", expanded_queries_text)
    progress_logs.append("\n==== 검색 프로세스 시작 ====")
    
    search_results = []
    for i, expanded_query in enumerate(expanded_queries, 1):
        progress_logs.append(f"\n---- 검색 {i}/{len(expanded_queries)} 시작 ----")
        progress_logs.append(f"[검색 쿼리] \"{expanded_query}\"")
        
        yield update_ui(f"   └ 검색 {i}/{len(expanded_queries)}: \"{expanded_query}\"", expanded_queries_text)
        
        # 검색 실행 및 로깅
        progress_logs.append("[검색 에이전트에 요청 전송 중...]")
        search_start_time = datetime.now()
        
        try:
            result = search_agent.run(expanded_query)
            search_time = (datetime.now() - search_start_time).total_seconds()
            
            # 검색 결과 로깅
            word_count = len(result.split())
            char_count = len(result)
            progress_logs.append(f"[검색 완료] 소요 시간: {search_time:.2f}초, 단어 수: {word_count}, 문자 수: {char_count}")
            progress_logs.append(f"[검색 결과 미리보기] {result[:150]}...")
            
            search_results.append({"query": expanded_query, "result": result})
            
            yield update_ui(f"     ↳ 검색 완료 ({word_count} 단어, {char_count} 글자, {search_time:.1f}초 소요)", expanded_queries_text)
            
        except Exception as e:
            progress_logs.append(f"[검색 오류 발생] {str(e)}")
            yield update_ui(f"     ↳ 검색 중 오류 발생: {str(e)}", expanded_queries_text)
        
        progress_logs.append(f"---- 검색 {i}/{len(expanded_queries)} 완료 ----")
    
    progress_logs.append("\n==== 검색 프로세스 완료 ====")
    
    # 3단계: 검색 결과 분석
    yield update_ui("\n3️⃣ 검색 결과를 분석하는 중...", expanded_queries_text)
    
    # 분석 과정에 로그 전달
    key_findings = analyze_results(analyzer_agent, search_results, progress_logs)
    findings_text = "\n".join([f"{i+1}. {finding}" for i, finding in enumerate(key_findings)])
    
    yield update_ui(f"✅ 분석 완료. {len(key_findings)}개의 핵심 발견사항 추출됨.", expanded_queries_text, findings_text)
    
    # 4단계: 보고서 생성 및 저장
    yield update_ui("\n4️⃣ 최종 보고서를 생성하는 중...", expanded_queries_text, findings_text)
    
    # 보고서 생성 과정에 로그 전달
    report = generate_report(writer_agent, query, key_findings, expanded_queries_text, progress_logs)
    
    # reports 디렉토리 생성
    progress_logs.append("\n[파일 시스템 작업] 'reports' 디렉토리 생성 중...")
    os.makedirs('reports', exist_ok=True)
    progress_logs.append("[파일 시스템 작업] 디렉토리 준비 완료")
    
    # 파일명에 타임스탬프 추가
    sanitized_query = "".join(c for c in query if c.isalnum() or c in ' -_').strip().replace(' ', '_')[:30]
    filename = f"report_{sanitized_query}_{timestamp}.txt"
    report_path = os.path.join('reports', filename)
    
    progress_logs.append(f"[파일 시스템 작업] 보고서 저장 준비 중: '{report_path}'")
    
    # 보고서 파일 저장
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    progress_logs.append(f"[파일 시스템 작업] 보고서 저장 완료: {len(report)} 자")
    
    # 로그 저장 마무리
    progress_logs.append("\n==== 프로세스 마무리 ====")
    progress_logs.append(f"[작업 완료 시간] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    progress_logs.append(f"[총 처리된 검색어] {len(expanded_queries)}개")
    progress_logs.append(f"[총 발견된 정보] {len(key_findings)}개")
    progress_logs.append(f"[최종 보고서 크기] {len(report)} 자")
    
    # 로그 파일 저장 (모든 raw 데이터 및 중간 과정 포함)
    log_path = save_logs_to_file(
        progress_logs, 
        query, 
        timestamp, 
        search_results=search_results,
        expanded_queries=expanded_queries_text,
        findings=findings_text,
        report=report
    )
    
    yield update_ui("\n✨ 작업이 완료되었습니다!", expanded_queries_text, findings_text, report, report_path, log_path)
    yield update_ui(f"📄 보고서가 '{report_path}' 파일에 저장되었습니다.", expanded_queries_text, findings_text, report, report_path, log_path)
    yield update_ui(f"📋 전체 과정 상세 로그가 '{log_path}' 파일에 저장되었습니다.", expanded_queries_text, findings_text, report, report_path, log_path)
    
    # 최종 결과 반환
    return (
        "\n".join(progress_logs[-15:]),  # UI에는 최근 15개 메시지만 표시
        expanded_queries_text,
        findings_text,
        report,
        report_path,
        log_path
    )

def create_gradio_interface():
    with gr.Blocks(title="멀티 에이전트 리서치 시스템", theme=gr.themes.Soft()) as interface:
        gr.Markdown("# 🤖 멀티 에이전트 리서치 시스템")
        gr.Markdown("검색하고 싶은 주제를 입력하면, AI 에이전트들이 협력하여 관련 정보를 수집하고 분석합니다.")
        
        with gr.Row():
            with gr.Column(scale=1):
                # 입력
                query_input = gr.Textbox(
                    label="검색 주제",
                    placeholder="예: 벚꽃 개화시기",
                    lines=2
                )
                search_button = gr.Button("🔍 검색 시작", variant="primary")
            
            with gr.Column(scale=2):
                # 진행 상황
                progress_output = gr.Textbox(
                    label="진행 상황",
                    lines=15,
                    interactive=False
                )
        
        with gr.Row():
            with gr.Column():
                # 확장된 쿼리
                expanded_queries_output = gr.Textbox(
                    label="확장된 검색어",
                    lines=5,
                    interactive=False
                )
                # 주요 발견사항
                findings_output = gr.Textbox(
                    label="주요 발견사항",
                    lines=10,
                    interactive=False
                )
            
            with gr.Column():
                # 최종 보고서
                report_output = gr.Textbox(
                    label="최종 보고서",
                    lines=20,
                    interactive=False
                )
                # 파일 다운로드
                with gr.Row():
                    # 보고서 파일 다운로드
                    file_output = gr.File(
                        label="보고서 다운로드",
                        interactive=False
                    )
                    # 로그 파일 다운로드
                    log_file_output = gr.File(
                        label="로그 다운로드",
                        interactive=False
                    )
        
        # 이벤트 연결
        search_button.click(
            fn=process_query,
            inputs=query_input,
            outputs=[
                progress_output,
                expanded_queries_output,
                findings_output,
                report_output,
                file_output,
                log_file_output
            ],
            show_progress=False
        )
    
    return interface

if __name__ == "__main__":
    interface = create_gradio_interface()
    interface.launch(
        server_name="0.0.0.0",
        share=True,
        show_error=True
    ) 