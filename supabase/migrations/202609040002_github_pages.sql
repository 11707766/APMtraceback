CREATE TABLE public.app_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('developer', 'tester')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE FUNCTION public.create_app_profile()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    INSERT INTO public.app_profiles (id, full_name, role)
    VALUES (NEW.id, COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.email), COALESCE(NEW.raw_user_meta_data->>'role', 'tester'));
    RETURN NEW;
END;
$$;

CREATE TRIGGER create_app_profile_after_signup
AFTER INSERT ON auth.users FOR EACH ROW EXECUTE FUNCTION public.create_app_profile();

CREATE TABLE public.app_change_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    requirement_signal_id TEXT NOT NULL,
    function_name TEXT NOT NULL,
    previous_value TEXT NOT NULL,
    new_value TEXT NOT NULL,
    developer_id UUID NOT NULL REFERENCES public.app_profiles(id),
    developer_name TEXT NOT NULL,
    tester_name TEXT NOT NULL,
    tester_email TEXT NOT NULL,
    reason TEXT NOT NULL,
    priority TEXT NOT NULL CHECK (priority IN ('Low', 'Medium', 'High', 'Critical')),
    status TEXT NOT NULL DEFAULT 'New' CHECK (status IN ('New', 'In Review', 'Approved', 'Rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.app_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.app_change_requests ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Authenticated users can view profiles" ON public.app_profiles FOR SELECT TO authenticated USING (true);
CREATE POLICY "Users can view assigned requests" ON public.app_change_requests FOR SELECT TO authenticated USING (developer_id = auth.uid() OR lower(tester_email) = lower(auth.jwt() ->> 'email'));
CREATE POLICY "Developers can create requests" ON public.app_change_requests FOR INSERT TO authenticated WITH CHECK (developer_id = auth.uid() AND EXISTS (SELECT 1 FROM public.app_profiles WHERE id = auth.uid() AND role = 'developer'));
CREATE POLICY "Assigned testers can update requests" ON public.app_change_requests FOR UPDATE TO authenticated USING (lower(tester_email) = lower(auth.jwt() ->> 'email')) WITH CHECK (lower(tester_email) = lower(auth.jwt() ->> 'email'));