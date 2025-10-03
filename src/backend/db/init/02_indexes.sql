-- Часто фильтруем по статусу и времени старта
create index if not exists idx_sessions_status_started
  on sessions (status, started_at);

-- Быстрый поиск сессий по user_id/started_at
create index if not exists idx_sessions_user_started
  on sessions (user_id, started_at desc);
