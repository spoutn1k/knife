API_KEY=AIzaSyAUjQF3g4Bj8CeeJD4ahlMWU5r2LshZT5s
TOKEN=$(curl -s "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=$API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"email":"jb.skutnik@gmail.com","password":"testtest","returnSecureToken":true}' | jq -r .idToken)
echo $TOKEN
curl -H "Authorization: Bearer $TOKEN" https://knife-c51d5.web.app/api/me
