from smac.env import StarCraft2Env
from torch.utils.tensorboard import SummaryWriter
import numpy as np
import json
import torch
import sys
from Agent import VDNAgent,MQAgent,JALAgent
from episode_buffer import EpisodeBuffer
from runnner import Runner
from learner import Learner
from controller import Controller
from writter_util import WritterUtil

class Args:
    pass

def main(args):

    path_checkpt = 'checkpoints/'+ args.run_name+ '.tar'
    if args.start_type == 'continue':
        run_state = torch.load(path_checkpt)
        args = run_state['args']
        args.start_type = 'continue'

    env = StarCraft2Env(map_name=args.map_name)
    env_info = env.get_env_info()

    n_actions = env_info["n_actions"]
    n_agents = env_info["n_agents"]
    
    args.n_agents = n_agents
    args.n_actions = n_actions
    args.input_dim = env_info['obs_shape']
    args.episode_limit = env_info['episode_limit']
    if args.model == 'mq':
        sys_agent = MQAgent(args)
    elif args.model == 'mq2':
        sys_agent = MQAgent2(args)
    elif args.model == 'jal':
        sys_agent = JALAgent(args)
    else:
        sys_agent = VDNAgent(args)

    if args.device == 'cuda':        
        sys_agent.cuda()
    
    writter = SummaryWriter('runs/'+ args.run_name)
    w_util = WritterUtil(writter,args)

    ctrler = Controller(sys_agent,args)
    runner = Runner(env,ctrler,args)
    learner = Learner(sys_agent, args)
    scheme = {}
    scheme['obs'] = {'shape':(n_agents,args.input_dim), 'dtype': torch.float32}
    scheme['valid'] = {'shape':(), 'dtype': torch.int32}
    scheme['actions'] = {'shape':(n_agents,), 'dtype': torch.int32}
    scheme['avail_actions'] = {'shape':(n_agents, n_actions), 'dtype': torch.int32}
    scheme['reward'] = {'shape':(), 'dtype': torch.float32}
    scheme['explores'] = {'shape':(n_agents,), 'dtype': torch.int32}
    scheme['learns'] = {'shape':(n_agents,), 'dtype': torch.int32}

    buffer = EpisodeBuffer(scheme, args)    
    loss = None
    e = 0
    if args.start_type == 'continue':
        e = run_state['episode'] + 1
        sys_agent.load_state_dict(run_state['model_state'])
        learner.optimizer.load_state_dict(run_state['optim_state'])
        buffer.load_state_dict(run_state['buffer_state'])


    for e in range(e ,args.n_episodes):
        
        data, episode_reward =  runner.run()        
        buffer.add_episode(data)        
        data = buffer.sample(args.n_batch)        
        w_util.WriteScalar('train/reward', episode_reward, e)
        if data:
            loss = learner.train(data)                        
            w_util.WriteScalar('train/loss', loss, e)
        print("Episode {}, reward = {}， loss = {}".format(e, episode_reward, loss))
        if e % args.test_every == 0:
            win_count = 0
            reward_avg = 0
            for i in range(args.test_count):
                _, episode_reward =  runner.run(test_mode=True)
                if episode_reward > 18:
                    win_count += 1
                reward_avg += episode_reward                
            win_rate = win_count/args.test_count
            reward_avg /= args.test_count
            w_util.WriteScalar('test/reward_avg', reward_avg, e)
            w_util.WriteScalar('test/win_rate', win_rate, e)
            
            print('Test reward = {}, win_rate = {}'.format(reward_avg, win_rate))

        if e % args.log_every == 0:
            w_util.WriteModel('model', sys_agent, e)
            run_state = {}
            run_state['args'] = args
            run_state['model_state'] = sys_agent.state_dict()
            run_state['optim_state'] = learner.optimizer.state_dict()
            run_state['episode'] = e            
            run_state['buffer_state'] = buffer.state_dict()
            torch.save(run_state, path_checkpt)
            

    env.close()

if __name__ == "__main__":

    # args = Args()
    # args.map_name = '3m'
    # args.msg_dim = 32
    # args.rnn_hidden_dim = 128
    # args.hub_hidden_dim = 128
    # args.gamma = 0.99
    # args.lr = 1e-3
    # args.l2 = 0
    # args.target_update = 10
    # args.epsilon = 0.1
    # args.test_every = 10
    # args.test_count = 10
    # args.device = 'cuda'
    # args.hidden_dim = 512
    # args.explore_type = 'independent'    #solo, independent, sync
    # args.learn_mask = False
    # args.agent_index = True
    # args.explore_action = True
    # args.n_batch = 8
    # args.buffer_size = 256
    # args.log_every = 20
    # args.log_num = None
    # args.n_episodes = 50
    # args.run_name = 'test_checkpt'
    # args.start_type = 'continue'   #new continue
    # args.model = 'mq'

    config_path='config.json'
    argv = sys.argv
    if len(argv)>1:
        config_path = argv[1]

    with open(config_path, 'r') as f:
        config = json.load(f)
    args = Args()
    args.__dict__.update(config)
    main(args)

    
