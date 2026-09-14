# QA 드라이버 보완

message-errors까지실제UI/서버대조통과. conversation-errors는대화삭제아이콘버튼이0×0이라pointer click이핸들러를열지못했다. qa-full-box.txt로크기를확인했고,같은실제button에focus→Enter하면확인모달이정상열렸다(qa-full-key-result.txt). 외부아이콘폰트가차단된격리환경이므로키보드활성화로검수한다. JS로DOM/상태를조작하지않는다. 처음실패한증거를덮지않도록retry파일prefix를사용한다. 제품소스변경없음.
