import sys, time, os, io, contextlib
sys.path.insert(0, os.getcwd()); sys.path.insert(0, os.path.join(os.getcwd(), "test"))
import slot_machine_test as st
import treasure_vault, slot_machine
with st.app.test_request_context():
    user = st.setup_session(tokens=0)
    t = time.time()
    with contextlib.redirect_stdout(io.StringIO()):
        for _ in range(2000):
            slot_machine.spin_response(slot_machine.MODE_BUY)
    print("slot", (time.time() - t) / 2000)
    st.session["user_object"]["userInfo"]["player"]["level"] = 30
    t = time.time()
    with contextlib.redirect_stdout(io.StringIO()):
        for _ in range(2000):
            treasure_vault.spin_response(treasure_vault.MODE_BUY, 3)
    print("vault", (time.time() - t) / 2000)
