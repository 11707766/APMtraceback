create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  name text not null,
  email text not null unique,
  role text not null check (role in ('developer', 'tester')),
  created_at timestamptz not null default now()
);

create table public.change_requests (
  id uuid primary key default gen_random_uuid(),
  requirement_signal_id text not null,
  function_name text not null,
  previous_value text not null,
  new_value text not null,
  developer_id uuid not null references public.profiles(id),
  developer_name text not null,
  tester_id uuid not null references public.profiles(id),
  tester_name text not null,
  tester_email text not null,
  reason text not null,
  priority text not null check (priority in ('Low', 'Medium', 'High', 'Critical')),
  status text not null default 'New' check (status in ('New', 'In Review', 'Approved', 'Rejected')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.profiles enable row level security;
alter table public.change_requests enable row level security;
create policy "Authenticated users can view profiles" on public.profiles for select to authenticated using (true);
create policy "Authenticated users can view requests" on public.change_requests for select to authenticated using (true);

create function public.create_profile() returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, name, email, role)
  values (new.id, coalesce(new.raw_user_meta_data ->> 'name', ''), new.email, coalesce(new.raw_user_meta_data ->> 'role', 'tester'));
  return new;
end;
$$;
create trigger on_auth_user_created after insert on auth.users for each row execute procedure public.create_profile();

create function public.create_change_request(requirement_signal_id text, function_name text, previous_value text, new_value text, tester_id uuid, reason text, priority text)
returns uuid language plpgsql security definer set search_path = public as $$
declare developer public.profiles; tester public.profiles; new_id uuid;
begin
  select * into developer from public.profiles where id = auth.uid() and role = 'developer';
  select * into tester from public.profiles where id = create_change_request.tester_id and role = 'tester';
  if developer.id is null or tester.id is null then raise exception 'A developer must assign a registered tester'; end if;
  insert into public.change_requests (requirement_signal_id, function_name, previous_value, new_value, developer_id, developer_name, tester_id, tester_name, tester_email, reason, priority)
  values (create_change_request.requirement_signal_id, create_change_request.function_name, create_change_request.previous_value, create_change_request.new_value, developer.id, developer.name, tester.id, tester.name, tester.email, create_change_request.reason, create_change_request.priority) returning id into new_id;
  return new_id;
end;
$$;

create function public.update_change_request(request_id uuid, requirement_signal_id text, function_name text, previous_value text, new_value text, tester_id uuid, reason text, priority text)
returns void language plpgsql security definer set search_path = public as $$
declare tester public.profiles;
begin
  select * into tester from public.profiles where id = update_change_request.tester_id and role = 'tester';
  if tester.id is null then raise exception 'Select a registered tester'; end if;
  update public.change_requests set requirement_signal_id = update_change_request.requirement_signal_id, function_name = update_change_request.function_name, previous_value = update_change_request.previous_value, new_value = update_change_request.new_value, tester_id = tester.id, tester_name = tester.name, tester_email = tester.email, reason = update_change_request.reason, priority = update_change_request.priority, status = 'New', updated_at = now() where id = request_id and developer_id = auth.uid();
  if not found then raise exception 'Only the request owner can edit this request'; end if;
end;
$$;

create function public.set_request_status(request_id uuid, next_status text)
returns void language plpgsql security definer set search_path = public as $$
begin
  update public.change_requests set status = next_status, updated_at = now() where id = request_id and tester_id = auth.uid() and next_status in ('New', 'In Review', 'Approved', 'Rejected');
  if not found then raise exception 'Only the assigned tester can update this request'; end if;
end;
$$;

create function public.delete_change_request(request_id uuid)
returns void language plpgsql security definer set search_path = public as $$
begin
  delete from public.change_requests where id = request_id and developer_id = auth.uid();
  if not found then raise exception 'Only the request owner can delete this request'; end if;
end;
$$;

grant execute on function public.create_change_request(text, text, text, text, uuid, text, text) to authenticated;
grant execute on function public.update_change_request(uuid, text, text, text, text, uuid, text, text) to authenticated;
grant execute on function public.set_request_status(uuid, text) to authenticated;
grant execute on function public.delete_change_request(uuid) to authenticated;