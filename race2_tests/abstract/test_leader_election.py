# no leader election, start election
# if timeout - start election
# no timeout -
def process(event: None):
    state = None
    match state:
        case LeaderElection():
            match event:
                case Heartbeat:
                    pass
        case Leader():
            pass
        case Follower():
            pass
    pass
