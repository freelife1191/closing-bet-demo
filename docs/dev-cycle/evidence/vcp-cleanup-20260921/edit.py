"""One-shot source edits for reviewed cleanup; no product execution."""
from pathlib import Path
import ast
p=Path('engine/vcp_ai_analyzer_helpers.py');s=p.read_text()
s=s.replace('from engine.', 'from engine.',1)
# Insert next to existing imports, without importing the product in this process.
pos=s.index('\nfrom engine.')
s=s[:pos]+'\nfrom engine.pandas_utils_safe import safe_confidence'+s[pos:]
a=s.index('def _normalize_confidence_value(');b=s.index('def _extract_json_fenced_content',a);s=s[:a]+s[b:]
s=s.replace('_normalize_confidence_value(confidence_match.group(1), default=0)','safe_confidence(confidence_match.group(1))').replace('_normalize_confidence_value(parsed.get("confidence"), default=0)','safe_confidence(parsed.get("confidence"))')
a=s.index('def is_low_quality_recommendation');b=s.index('def _normalize_reason_value',a)
s=s[:a]+s[a:b].replace('except (TypeError, ValueError):','except (TypeError, ValueError, OverflowError):')+s[b:];p.write_text(s)
p=Path('engine/vcp_ai_analyzer.py');s=p.read_text();tree=ast.parse(s);lines=s.splitlines(keepends=True)
nodes=[n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and (n.name=='_fallback_to_zai' or (n.name=='_extract_status_code' and n.col_offset==8))]
for n in sorted(nodes,key=lambda n:n.lineno,reverse=True):del lines[n.lineno-1:n.end_lineno]
s=''.join(lines)
s=s.replace('def _extract_status_code(self, error: Exception) -> int | None:', 'def _extract_status_code(self, error: Exception, *, include_code: bool = True) -> int | None:')
s=s.replace('        for attr in ("status_code", "http_status", "code"):', '        attrs = ("status_code", "http_status", "code") if include_code else ("status_code", "http_status")\n        for attr in attrs:')
s=s.replace('status_code = _extract_status_code(error)', 'status_code = self._extract_status_code(error)')
a=s.index('    async def _analyze_with_zai');b=s.index('    def _build_perplexity_fallback_chain',a)
z=s[a:b].replace('self._extract_status_code(error)', 'self._extract_status_code(error, include_code=False)')
z=z.replace('            max_parse_attempts = 1\n','').replace('attempt_timeout = request_timeout + (attempt * 20.0)','attempt_timeout = request_timeout').replace('attempt={attempt+1}/{max_parse_attempts}', 'attempt=1').replace('attempt={attempt+1}', 'attempt=1')
# Identify breaks whose nearest enclosing loop is the single-attempt loop.
tree=ast.parse(s[a:b].replace('    async def','async def',1)) if False else ast.parse(s)
zlines=z.splitlines(keepends=True)
# Parse the method as a class body to retain its source indentation.
t=ast.parse('class Holder:\n'+z); inner=next(n for n in ast.walk(t) if isinstance(n,ast.For) and isinstance(n.target,ast.Name) and n.target.id=='attempt')
breaks=[]
def walk(n,active):
 if isinstance(n,ast.Break) and active is inner:breaks.append(n.lineno-2)
 for ch in ast.iter_child_nodes(n):walk(ch,n if isinstance(n,(ast.For,ast.While)) else active)
walk(inner,None)
for idx in sorted(breaks,reverse=True):
 indent=zlines[idx][:len(zlines[idx])-len(zlines[idx].lstrip())]
 zlines[idx]=indent+'if should_try_next_model:\n'+indent+'    continue\n'+indent+'break\n'
z=''.join(zlines)
start=z.index('                for attempt in range(max_parse_attempts):\n');end=z.index('\n                if should_try_next_model:\n', start)
block=z[start+len('                for attempt in range(max_parse_attempts):\n'):end]
block=''.join(line[4:] if line.startswith('    ') else line for line in block.splitlines(keepends=True))
z=z[:start]+block+z[end:]
z=z.replace('\n                if should_try_next_model:\n                    continue\n                break\n','\n',1)
s=s[:a]+z+s[b:]
a=s.index('        for provider in source:',s.index('    def _build_perplexity_fallback_chain'));b=s.index('        return chain',a);s=s[:a]+s[b:]
s=s.replace('        if allowed_chain:\n            return allowed_chain\n\n        # fallback 대상은 반드시 VCP_AI_PROVIDERS 설정값 기반으로만 결정한다.\n        return []','        # fallback 대상은 반드시 VCP_AI_PROVIDERS 설정값 기반으로만 결정한다.\n        return allowed_chain')
ast.parse(s);p.write_text(s)
p=Path('scripts/init_data.py');s=p.read_text();lines=s.splitlines(keepends=True)
names={'assign_grade','create_market_gate','reset_cache','get_market_indices','get_sector_indices','fetch_market_indices','fetch_sector_indices'}
for n in sorted([n for n in ast.parse(s).body if isinstance(n,ast.FunctionDef) and n.name in names],key=lambda n:n.lineno,reverse=True):del lines[n.lineno-1:n.end_lineno]
s=''.join(lines).replace('# 전역 캐시 (여러 함수에서 공유)\n_market_indices_cache = None\n_sector_indices_cache = None\n','')
# Only collapse gaps left by deletion.
while '\n\n\n\n' in s:s=s.replace('\n\n\n\n','\n\n\n')
ast.parse(s);p.write_text(s)
Path('tests/test_grading_logic.py').unlink()
