최초git diff --cached --check는 raw diff의문맥공백과리뷰Markdown줄끝공백때문에exit2. 커밋안함. 원본bytes를gzip+SHA로보존하고표시문서공백만정리한후재검사. 제품소스불변.
마감검사도설명문서2개의빈EOF로exit2. 본문불변으로끝빈줄만제거후재검사. 별도증거검증PASS가이git검사실패를대체하지않으며커밋은재검사후에만수행.
