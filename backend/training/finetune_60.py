"""Continue training inside this project; no external project paths."""
from pathlib import Path
import argparse,json,os
BACKEND=Path(__file__).resolve().parents[1]
os.environ.setdefault('YOLO_CONFIG_DIR',str(BACKEND/'data/training/ultralytics_config'))
from ultralytics import YOLO
from training.preserve_checkpoint import PreserveCheckpointTrainer

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--epochs',type=int,default=10)
    ap.add_argument('--name',required=True)
    ap.add_argument('--weights',default=None)
    args=ap.parse_args()
    if args.epochs<1 or Path(args.name).name!=args.name:
        ap.error('Use positive epochs and a single run-folder name.')
    status=json.loads((BACKEND/'data/training/status.json').read_text(encoding='utf-8'))
    weights=Path(args.weights or status['checkpoint'])
    if not weights.is_absolute():weights=BACKEND/weights
    project=BACKEND/'data/training/yolo_runs'
    if (project/args.name).exists():raise FileExistsError('Choose a new run name; existing weights will not be overwritten.')
    data=BACKEND/'data/yolo/combined/data.yaml'
    model=YOLO(str(weights))
    model.train(trainer=PreserveCheckpointTrainer,data=str(data),epochs=args.epochs,imgsz=1024,batch=1,
                device=0,workers=0,amp=False,plots=False,cache=False,optimizer='AdamW',lr0=1e-5,
                warmup_epochs=0,warmup_bias_lr=0,mosaic=0,close_mosaic=0,seed=42,deterministic=True,
                max_det=1000,iou=.6,val=True,project=str(project),name=args.name,exist_ok=False)
    m=YOLO(str(project/args.name/'weights/best.pt')).val(data=str(data),split='test',imgsz=1024,
                batch=1,device=0,workers=0,plots=False,max_det=1000,project=str(project),name=args.name+'_test')
    (project/args.name/'test_metrics.json').write_text(json.dumps({'map50':float(m.box.map50),
        'map50_95':float(m.box.map),'precision':float(m.box.mp),'recall':float(m.box.mr)},indent=2),encoding='utf-8')
    print('Training complete. The active application model has not been changed.')

if __name__=='__main__':main()
