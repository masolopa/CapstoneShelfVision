"""Preserve the exact checkpoint architecture for same-class fine-tuning.

Rebuilding a remapped YOLO head from YAML can silently discard learned tensors.
The callback verifies every state entry immediately before the first epoch.
"""
import copy
import json
from pathlib import Path

import torch
from ultralytics.models.yolo.detect.train import DetectionTrainer


class PreserveCheckpointTrainer(DetectionTrainer):
    def get_model(self, cfg=None, weights=None, verbose=True):
        if weights is None or weights.model[-1].nc != self.data['nc']:
            # Scratch training or deliberate transfer to a different class count.
            return super().get_model(cfg=cfg, weights=weights, verbose=verbose)
        source = weights.float()
        if source.names != self.data['names']:
            raise ValueError('Checkpoint class names/order differ from the dataset.')
        model = copy.deepcopy(source)
        # Loss helpers may contain plain tensors restored on CPU by torch.load.
        # They are not model weights; rebuild them lazily on the training device.
        if hasattr(model, 'criterion'):
            model.criterion = None
        self._source_state = {k: v.detach().cpu().clone() for k, v in source.state_dict().items()}
        target = model.state_dict()
        if target.keys() != self._source_state.keys() or any(
            not torch.equal(v, target[k].detach().cpu()) for k, v in self._source_state.items()
        ):
            raise RuntimeError('Checkpoint was not copied exactly; refusing to train.')
        self.add_callback('on_train_start', verify_initial_weights)
        return model


def verify_initial_weights(trainer):
    source = trainer._source_state
    current = trainer.model.state_dict()
    different = [k for k, v in source.items() if k not in current or not torch.equal(v, current[k].detach().cpu())]
    if source.keys() != current.keys() or different:
        raise RuntimeError(f'Weights changed before training: {different}')
    proof = {'original_entries': len(source), 'identical_entries': len(current),
             'different_entries': different, 'check': 'torch.equal before first epoch',
             'checkpoint': str(trainer.args.model)}
    (Path(trainer.save_dir) / 'initial_weights_verified.json').write_text(json.dumps(proof, indent=2), encoding='utf-8')
    print(f'VERIFIED: {len(current)}/{len(source)} checkpoint entries identical before training.', flush=True)
    del trainer._source_state
