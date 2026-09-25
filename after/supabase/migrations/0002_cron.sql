-- 24시간/7일 자동 삭제 크론.
-- pg_cron 이 30분마다 Next.js 의 /api/cron/cleanup 을 호출한다.
-- storage.objects 행만 지우면 실제 파일이 남기 때문에 삭제는 서버 라우트가 service role 로 수행한다.
--
-- 적용 전에 아래 두 값을 바꿔라:
--   __CLEANUP_URL__  → https://<배포 도메인>/api/cron/cleanup
--   __CRON_SECRET__  → .env 의 CRON_SECRET 과 같은 값
-- Supabase 대시보드 > Database > Extensions 에서 pg_cron, pg_net 이 켜져 있어야 한다.

create extension if not exists pg_cron;
create extension if not exists pg_net;

select cron.unschedule('after-cleanup') where exists (select 1 from cron.job where jobname = 'after-cleanup');

select cron.schedule(
  'after-cleanup',
  '*/30 * * * *',
  $$
  select net.http_post(
    url := '__CLEANUP_URL__',
    headers := jsonb_build_object('Authorization', 'Bearer __CRON_SECRET__', 'Content-Type', 'application/json'),
    body := '{}'::jsonb
  );
  $$
);
