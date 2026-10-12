import sys, json
from ultralytics import YOLO
t=sys.argv[1]
m=YOLO(t+'/best.pt')
r=m.val(data=t+'/data.yaml', split='test', imgsz=640, batch=16, device='cpu', plots=False, project=t+'/out', name='test_eval', verbose=True, workers=0)
d={'precision':float(r.box.mp),'recall':float(r.box.mr),'mAP50':float(r.box.map50),'mAP50_95':float(r.box.map)}
per={r.names[c]:{'AP50':float(r.box.ap50[i]),'AP50_95':float(r.box.ap[i])} for i,c in enumerate(r.box.ap_class_index)}
json.dump({'overall':d,'per_class':per,'speed_ms':r.speed},open(t+'/test_metrics.json','w'),indent=1)
print(json.dumps(d))
