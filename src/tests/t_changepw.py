from k5test import *

# Also listen on a UNIX domain sockets for kpasswd.
unix_conf = {'realms': {'$realm': {
    'kdc_listen': '$port0, $testdir/krb5.sock',
    'kadmind_listen': '$port1, $testdir/kadmin.sock',
    'kpasswd_listen': '$port2, $testdir/kpasswd.sock'}}}
realm = K5Realm(create_host=False,get_creds=False, kdc_conf=unix_conf)
realm.start_kadmind()
realm.prep_kadmin()

# Mark a principal as expired and change its password through kinit.
mark('password change via kinit')
realm.run([kadminl, 'modprinc', '-pwexpire', '1 day ago', 'user'])
pwinput = password('user') + '\nabcd\nabcd\n'
realm.run([kinit, realm.user_princ], input=pwinput)

# Regression test for #7868 (preauth options ignored when
# krb5_get_init_creds_password() initiates a password change).  This
# time use the REQUIRES_PWCHANGE bit instead of the password
# expiration time.
mark('password change via kinit with FAST')
realm.run([kadminl, 'modprinc', '+needchange', 'user'])
pwinput = 'abcd\nefgh\nefgh\n'
out, trace = realm.run([kinit, '-T', realm.ccache, realm.user_princ],
                       input=pwinput, return_trace=True)
# Check that FAST was used when getting the kadmin/changepw ticket.
getting_changepw = fast_used_for_changepw = False
for line in trace.splitlines():
    if 'Getting initial credentials for user@' in line:
        getting_changepw_ticket = False
    if 'Setting initial creds service to kadmin/changepw' in line:
        getting_changepw_ticket = True
    if getting_changepw_ticket and 'Using FAST' in line:
        fast_used_for_changepw = True
if not fast_used_for_changepw:
    fail('FAST was not used to get kadmin/changepw ticket')

# Test that passwords specified via kadmin and kpasswd are usable with
# kinit.
mark('password change usability by kinit')
realm.run([kadminl, 'addprinc', '-pw', 'pw1', 'testprinc'])
# Run kpasswd with an active cache to exercise automatic FAST use.
realm.kinit('testprinc', 'pw1')
realm.run([kpasswd, 'testprinc'], input='pw1\npw2\npw2\n')
realm.kinit('testprinc', 'pw2')
realm.run([kdestroy])
realm.run([kpasswd, 'testprinc'], input='pw2\npw3\npw3\n')
realm.kinit('testprinc', 'pw3')
realm.run([kdestroy])
realm.run_kadmin(['cpw', '-pw', 'pw4', 'testprinc'])
realm.kinit('testprinc', 'pw4')
realm.run([kdestroy])
realm.run([kadminl, 'delprinc', 'testprinc'])

mark('password change over UNIX domain socket')

unix_cli_conf = {'realms': {'$realm': {
    'kdc': '$testdir/krb5.sock',
    'admin_server': '$testdir/kadmin.sock',
    'kpasswd_server': '$testdir/kpasswd.sock'}}}
unix_cli = realm.special_env('unix_cli', False, krb5_conf=unix_cli_conf)

realm.run([kadminl, 'addprinc', '-pw', 'pw1', 'testprinc'])
msgs = ('Sending TCP request to UNIX domain socket',)
realm.run([kpasswd, 'testprinc'], input='pw1\npw2\npw2\n', env=unix_cli,
          expected_trace=msgs)
realm.run([kadminl, 'delprinc', 'testprinc'])

success('Password change tests')
