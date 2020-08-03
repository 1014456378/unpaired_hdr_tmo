import torch
import torch.optim as optim

import GanTrainer
import config
import utils.model_save_util as model_save_util
from utils import printer, params

if __name__ == '__main__':
    opt = config.get_opt()
    printer.print_opt(opt)

    net_G = model_save_util.create_G_net(opt.model, opt.device, opt.checkpoint, opt.input_dim, opt.last_layer,
                                         opt.filters, opt.con_operator, opt.unet_depth, opt.add_frame,
                                         opt.unet_norm, opt.add_clipping, opt.g_activation, opt.use_xaviar,
                                         opt.output_dim, opt.apply_exp)
    net_D = model_save_util.create_D_net(opt.output_dim, opt.d_down_dim, opt.device, opt.checkpoint, opt.d_norm,
                                         opt.use_xaviar, opt.d_model, opt.d_nlayers, opt.d_last_activation)

    printer.print_net("G add frame", net_G, opt, input_size=364)
    printer.print_net("G", net_G, opt, input_size=256)
    printer.print_net("D", net_D, opt, input_size=256)

    # Setup Adam optimizers for both G and D
    optimizer_D = optim.Adam(net_D.parameters(), lr=opt.D_lr, betas=(params.beta1, 0.999))
    optimizer_G = optim.Adam(net_G.parameters(), lr=opt.G_lr, betas=(params.beta1, 0.999))

    step_gamma = 0.5 ** (1 / opt.lr_decay_step)
    lr_scheduler_D = torch.optim.lr_scheduler.StepLR(optimizer=optimizer_D, step_size=1, gamma=step_gamma)
    lr_scheduler_G = torch.optim.lr_scheduler.StepLR(optimizer=optimizer_G, step_size=1, gamma=step_gamma)

    # lr_scheduler_D = torch.optim.lr_scheduler.MultiStepLR(optimizer=optimizer_D, milestones=opt.milestones)
    # lr_scheduler_G = torch.optim.lr_scheduler.MultiStepLR(optimizer=optimizer_G, milestones=opt.milestones)

    gan_trainer = GanTrainer.GanTrainer(opt, net_G, net_D, optimizer_G, optimizer_D, lr_scheduler_G, lr_scheduler_D)
    gan_trainer.train()
