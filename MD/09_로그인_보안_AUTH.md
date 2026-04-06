# 09 로그인 / 보안 구조 (AUTH)

---

## 개요

| 항목 | 내용 |
|------|------|
| **인증 방식** | 이메일 OTP (6자리 코드) |
| **인증 서비스** | Supabase Auth |
| **이메일 발송** | Gmail SMTP (smtp.gmail.com:587) |
| **세션 방식** | implicit flow (`flowType: 'implicit'`) |
| **역할 저장** | Supabase `user_roles` 테이블 |
| **메뉴 설정 저장** | Supabase `menu_settings` 테이블 |

---

## 역할(Role) 체계

| 역할 | 레벨 | 접근 범위 |
|------|------|----------|
| `admin` | 3 | 전체 메뉴 + 구성원 관리 + 메뉴 관리 |
| `member` | 2 | 관리자가 허용한 메뉴 |
| `user` | 1 | 번역기 전용 (비로그인 상태) |

---

## 이메일 허용 도메인

```javascript
const allowed = email === 'jeehoon.eddie@gmail.com'
             || email.endsWith('@nationalmotors.co.kr');
```

- `@nationalmotors.co.kr` 도메인만 OTP 발송 허용
- 예외: `jeehoon.eddie@gmail.com` (개발자 계정)
- 그 외 이메일은 OTP 발송 전 프론트에서 차단

---

## 로그인 플로우

```
1. 이메일 입력 → 도메인 검증 (프론트)
        ↓ 통과
2. Supabase Auth signInWithOtp({ email })
        ↓
3. Gmail SMTP → 사용자 이메일로 6자리 OTP 발송
        ↓
4. OTP 입력 → /auth/v1/verify 직접 fetch
   (Supabase JS SDK verifyOtp() 우회 — PKCE hanging 이슈)
        ↓
5. access_token / refresh_token 수신
        ↓
6. user_roles 테이블에서 역할 조회
   (Bearer access_token 사용)
        ↓
7. 역할 없으면 → "등록되지 않은 사용자" 차단
   역할 있으면 → applyRole() 호출 → 로그인 완료
```

---

## Supabase 클라이언트 초기화

```javascript
const SUPABASE_URL = 'https://vbvghhtroitmroxmfepr.supabase.co';
const SUPABASE_KEY = '...anon key...';
const _sb = supabase.createClient(SUPABASE_URL, SUPABASE_KEY, {
  auth: { flowType: 'implicit' }
});
```

- `flowType: 'implicit'` — PKCE 대신 implicit 사용 (PKCE는 verifyOtp hanging 발생)
- `SUPABASE_KEY`는 anon key (공개 가능, RLS로 보호)

---

## 토큰 관리

```javascript
let _accessToken = '';  // 전역 변수

// verifyOtp 성공 시 저장
_accessToken = resData.access_token;

// _handleSession (세션 복원) 시 저장
if (session.access_token) _accessToken = session.access_token;
```

- `_accessToken`은 모든 Supabase REST API 인증 요청에 사용
- `_sb.auth.setSession()`은 non-blocking (hanging 방지)

---

## Supabase 테이블 구조

### user_roles

```sql
create table public.user_roles (
  email      text primary key,
  name       text,
  role       text,   -- 'admin' | 'member' | 'user'
  created_at timestamptz default now()
);
```

**RLS 정책:**

| 정책명 | 대상 | 조건 |
|--------|------|------|
| user_roles_select | SELECT | `email = auth.jwt()->>'email'` OR `my_role() = 'admin'` |
| admin 추가 | INSERT | `my_role() = 'admin'` |
| admin 수정 | UPDATE | `my_role() = 'admin'` |
| admin 삭제 | DELETE | `my_role() = 'admin'` |

> 핵심: 본인 행은 누구나 읽을 수 있어야 로그인 시 역할 확인 가능

---

### menu_settings

```sql
create table public.menu_settings (
  key        text primary key,  -- 'view-sales', 'view-top-defect' 등
  min_role   text not null default 'admin',  -- 'admin' | 'member' | 'all'
  hidden     boolean not null default false,
  updated_at timestamptz default now()
);
```

**RLS 정책:**

| 정책명 | 대상 | 조건 |
|--------|------|------|
| menu_settings_select | SELECT | `true` (전체 공개 읽기) |
| menu_settings_write | ALL | `my_role() = 'admin'` |

---

### my_role() 함수

```sql
create or replace function public.my_role()
returns text language sql security definer stable as $$
  select role from public.user_roles
  where email = auth.jwt() ->> 'email' limit 1;
$$;
```

- `security definer`: RLS 우회 권한으로 실행 (재귀 무한루프 방지)
- RLS 정책 내에서 현재 사용자 역할을 안전하게 조회하는 용도

---

## 메뉴 권한 제어 구조

### 역할 레벨

```javascript
const ROLE_LEVEL    = { admin: 3, member: 2, user: 1 };
const MINROLE_LEVEL = { admin: 3, member: 2, all: 1 };
```

### 메뉴 로드 우선순위

```
1순위: Supabase menu_settings (anon key로 공개 읽기)
2순위: localStorage 캐시
3순위: DEFAULT_MENU_CFG (코드 내 기본값 — 전부 admin)
```

### 메뉴 저장 흐름 (관리자)

```
메뉴 관리 화면에서 설정 변경
    → 저장 & 적용 클릭
    → localStorage 캐시 저장
    → Supabase menu_settings DELETE 후 INSERT
    → applyMenuCfg() 즉시 적용 (현재 세션)
```

### 메뉴 적용 흐름 (구성원 로그인 시)

```
applyRole('member', account)
    → loadMenuCfg() → Supabase menu_settings 조회
    → applyMenuCfg(cfg, 'member')
    → userLevel(2) >= minRoleLevel 비교
    → 조건 충족 메뉴만 사이드바 표시
```

---

## 발생했던 주요 오류 및 해결

### 1. Supabase JS verifyOtp() hanging
- **원인**: PKCE flow에서 code exchange 내부적으로 무한 대기
- **해결**: `/auth/v1/verify` 엔드포인트에 직접 fetch, JS SDK verifyOtp() 완전 우회

### 2. setSession() hanging
- **원인**: `onAuthStateChange` → `_handleSession` → `user_roles` 쿼리 순환 블로킹
- **해결**: `setSession().catch(()=>{})` non-blocking 처리, 역할 조회는 직접 fetch로 분리

### 3. RLS 재귀 무한루프
- **원인**: `user_roles` SELECT 정책 내에서 `user_roles`를 다시 조회
- **해결**: `security definer` 함수 `my_role()` 생성 → RLS 우회하여 역할 조회

### 4. 이메일 발송 실패 (Resend SMTP)
- **원인**: Resend는 계정 소유자 이메일 외 수신 불가 (onboarding@resend.dev 발신 제한)
- **해결**: Gmail SMTP (smtp.gmail.com:587, 앱 비밀번호)로 교체

### 5. OTP 8자리 발송
- **원인**: Supabase 기본 OTP 길이 8자리, 이메일 템플릿 `{{ .SixDigitOtp }}` 미사용
- **해결**: OTP 길이 6자리로 변경 + 템플릿 `{{ .Token }}` 사용

### 6. 구성원 로그인 불가 (user_roles SELECT 차단)
- **원인**: SELECT 정책이 `my_role() = 'admin'`만 허용 → 구성원이 본인 행 조회 불가
- **해결**: `email = auth.jwt()->>'email' OR my_role() = 'admin'` 조건으로 수정

### 7. 메뉴 설정이 구성원에게 미적용
- **원인**: `menu_settings`를 localStorage에만 저장 → 다른 브라우저/기기에 미전파
- **해결**: Supabase `menu_settings` 테이블에 저장, 로그인 시 Supabase에서 로드

### 8. 메뉴 저장 실패 (accessToken 없음)
- **원인**: 페이지 새로고침 시 `_handleSession`이 `_accessToken`을 저장 안 함
- **해결**: `_handleSession`에서 `_accessToken = session.access_token` 추가

### 9. 메뉴 저장 오류 (All object keys must match)
- **원인**: PostgREST upsert (`resolution=merge-duplicates`) 방식 호환 문제
- **해결**: DELETE 후 INSERT 방식으로 교체, 데이터 타입 명시적 변환 추가

---

## 등록된 계정 (2026-03-31 기준)

| 이메일 | 역할 | 비고 |
|--------|------|------|
| jhl@nationalmotors.co.kr | admin | 관리자 |
| jeehoon.eddie@gmail.com | admin | 개발자 테스트 |

> 구성원 추가는 대시보드 **구성원 관리** 화면에서 진행

---

## Supabase 프로젝트 정보

| 항목 | 값 |
|------|-----|
| Project URL | https://vbvghhtroitmroxmfepr.supabase.co |
| 이메일 SMTP | Gmail (smtp.gmail.com:587) |
| Auth 방식 | Email OTP (Confirm email 비활성화) |
