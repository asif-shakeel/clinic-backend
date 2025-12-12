from supabase import create_client
import os

supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_ANON_KEY"],
)

email = "asif.shakeel@gmail.com"
password = "Sandiego25?"

res = supabase.auth.sign_in_with_password({
    "email": email,
    "password": password
})

print(res.session.access_token)
