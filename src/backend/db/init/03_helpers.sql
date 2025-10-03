-- Удобные upsert-операции

-- Обновление статуса сессии
create or replace function set_session_status(p_session uuid, p_status text)
returns void language plpgsql as $$
begin
  update sessions set status = p_status, stopped_at = case when p_status in ('stopped','error') then now() else stopped_at end
  where id = p_session;
end$$;