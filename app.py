from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import ga_engine, nsga2_engine, hashlib, time, os, json

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

PRICES = {
    "cost":{"price":20000,"name_ar":"تحسين التكلفة"},
    "time":{"price":20000,"name_ar":"تحسين الزمن"},
    "yield":{"price":20000,"name_ar":"تحسين المردود"},
    "cost_time":{"price":35000,"name_ar":"تكلفة + زمن"},
    "cost_time_yield":{"price":52500,"name_ar":"تكلفة + زمن + مردود"},
}

pay_db = {}
com_db = []
usr_db = {}
opt_db = []
ADMIN_EMAIL = "admin@intajia.dz"
ADMIN_HASH = hashlib.sha256("admin123".encode()).hexdigest()
DF = "data.json"

def save():
    try:
        with open(DF,'w',encoding='utf-8') as f:
            json.dump({"p":pay_db,"c":com_db,"u":usr_db,"o":opt_db},f,ensure_ascii=False)
    except: pass

def load():
    global pay_db,com_db,usr_db,opt_db
    try:
        if os.path.exists(DF):
            with open(DF,'r',encoding='utf-8') as f:
                d=json.load(f)
                pay_db,com_db,usr_db,opt_db=d.get("p",{}),d.get("c",[]),d.get("u",{}),d.get("o",[])
    except: pass

def is_admin(d):
    e,t=d.get('ae',''),d.get('at','')
    if e==ADMIN_EMAIL and t==ADMIN_HASH: return True
    return e in usr_db and usr_db[e].get("role")=="admin"

@app.route('/')
def idx(): return send_from_directory('static','index.html')

@app.route('/<path:p>')
def sf(p): return send_from_directory('static',p)

@app.route('/api/auth/register',methods=['POST'])
def reg():
    try:
        d=request.get_json()
        e,pw,n=d.get('email','').strip().lower(),d.get('password',''),d.get('name','')
        if not e or not pw: return jsonify({"success":False,"error":"مطلوب"}),400
        if e in usr_db: return jsonify({"success":False,"error":"مسجل مسبقاً"}),400
        uid=hashlib.sha256(f"{e}{time.time()}".encode()).hexdigest()[:12]
        usr_db[e]={"id":uid,"email":e,"name":n or e.split('@')[0],"ph":hashlib.sha256(pw.encode()).hexdigest(),"role":"admin" if e==ADMIN_EMAIL else "user","t":time.time(),"paid":False}
        save()
        return jsonify({"success":True,"user":{"id":uid,"email":e,"name":usr_db[e]["name"],"role":usr_db[e]["role"]}})
    except Exception as ex: return jsonify({"success":False,"error":str(ex)}),500

@app.route('/api/auth/login',methods=['POST'])
def log():
    try:
        d=request.get_json()
        e,pw=d.get('email','').strip().lower(),d.get('password','')
        h=hashlib.sha256(pw.encode()).hexdigest()
        if e==ADMIN_EMAIL and h==ADMIN_HASH: return jsonify({"success":True,"user":{"id":"admin","email":e,"name":"المشرف","role":"admin"}})
        if e not in usr_db or usr_db[e]["ph"]!=h: return jsonify({"success":False,"error":"خاطئ"}),401
        u=usr_db[e]
        return jsonify({"success":True,"user":{"id":u["id"],"email":e,"name":u["name"],"role":u["role"]}})
    except Exception as ex: return jsonify({"success":False,"error":str(ex)}),500

@app.route('/api/comments',methods=['GET'])
def gcom():
    ap=sorted([c for c in com_db if c.get("s")=="approved"],key=lambda x:x["t"],reverse=True)
    return jsonify({"success":True,"comments":ap})

@app.route('/api/comments',methods=['POST'])
def acom():
    try:
        d=request.get_json()
        nm,tx,em,rt=d.get('name','').strip(),d.get('text','').strip(),d.get('email',''),int(d.get('rating',5))
        if not nm or not tx: return jsonify({"success":False,"error":"مطلوب"}),400
        if len(tx)>500: return jsonify({"success":False,"error":"طويل جداً"}),400
        c={"id":hashlib.sha256(f"{nm}{time.time()}".encode()).hexdigest()[:10],"name":nm,"text":tx,"email":em,"rating":max(1,min(5,rt)),"s":"pending","t":time.time(),"replies":[]}
        com_db.append(c)
        save()
        return jsonify({"success":True,"message":"سيظهر بعد المراجعة","comment":c})
    except Exception as ex: return jsonify({"success":False,"error":str(ex)}),500

@app.route('/api/prices',methods=['GET'])
def gpr(): return jsonify({"success":True,"prices":PRICES})

@app.route('/api/payment/prepare',methods=['POST'])
def pprep():
    try:
        d=request.get_json()
        st=d.get('serviceType','cost')
        if st not in PRICES: return jsonify({"success":False,"error":"غير معروف"}),400
        tx=hashlib.sha256(f"{st}{time.time()}{os.urandom(8).hex()}".encode()).hexdigest()[:16].upper()
        pay_db[tx]={"st":st,"amt":PRICES[st]["price"],"s":"pending","em":d.get('email',''),"t":time.time()}
        save()
        return jsonify({"success":True,"transactionId":tx,"amount":PRICES[st]["price"],"serviceName":PRICES[st]["name_ar"],"currency":"DZD"})
    except Exception as ex: return jsonify({"success":False,"error":str(ex)}),500

@app.route('/api/payment/confirm',methods=['POST'])
def pconf():
    try:
        d=request.get_json()
        tx, mt=d.get('transactionId',''), d.get('method','ccp')

        if tx not in pay_db: return jsonify({"success":False,"error":"معاملة غير صالحة"}),400

        # وضع تجريبي: لا نجمع أي بيانات مصرفية حقيقية (رقم حساب أو PIN).
        if mt not in ('ccp','baridimob'):
            return jsonify({"success":False,"error":"طريقة دفع غير مدعومة"}),400

        pay_db[tx].update({"s":"confirmed","mt":mt,"ct":time.time(),"demo":True})

        em=pay_db[tx].get("em","")
        if em and em in usr_db: usr_db[em]["paid"]=True
        save()
        return jsonify({"success":True,"transactionId":tx,"message":"تم التأكيد (تجريبي)!","serviceType":pay_db[tx]["st"],"amount":pay_db[tx]["amt"]})
    except Exception as ex: return jsonify({"success":False,"error":str(ex)}),500

@app.route('/api/optimize',methods=['POST'])
def opt():
    try:
        d=request.get_json()
        if not d: return jsonify({"error":"No data"}),400
        nw,nt,ns=int(d.get('nWorkers')),int(d.get('nTasks')),int(d.get('nShifts'))
        cm,st=d.get('costMatrix'),d.get('serviceType','cost')
        if not all([nw,nt,ns,cm]): return jsonify({"error":"Missing"}),400
        tm,ym=d.get('timeMatrix'),d.get('yieldMatrix')
        wc,wt,wy=float(d.get('weightCost',.5)),float(d.get('weightTime',.5)),float(d.get('weightYield',0))

        if st=='cost_time':
            if not tm: return jsonify({"error":"timeMatrix مطلوبة"}),400
            wy=0
        elif st=='cost_time_yield':
            if not tm or not ym: return jsonify({"error":"timeMatrix+yieldMatrix مطلوبتان"}),400

        if st in ('cost_time','cost_time_yield'):
            tw=wc+wt+wy
            if tw>0: wc/=tw; wt/=tw; wy/=tw

        if st == 'cost_time':
            targets = ['cost', 'time']
            pareto_results = nsga2_engine.run_nsga2(nw, nt, ns, cm, tm, ym, targets)
            return jsonify({"success":True, "isPareto": True, "data": pareto_results}), 200

        elif st == 'cost_time_yield':
            targets = ['cost', 'time', 'yield']
            pareto_results = nsga2_engine.run_nsga2(nw, nt, ns, cm, tm, ym, targets)
            return jsonify({"success":True, "isPareto": True, "data": pareto_results}), 200

        else:
            r=ga_engine.run_ga(nw,nt,ns,cm,st,tm,ym,wc,wt,wy)
            opt_db.append({"id":hashlib.sha256(f"o{time.time()}".encode()).hexdigest()[:10],"em":d.get('email',''),"st":st,"p":{"w":nw,"t":nt,"s":ns},"r":{"c":r["bestCost"],"s":r["bestSolution"]},"t":time.time()})
            save()
            return jsonify({"success":True, "isPareto": False, "data":r}),200

    except Exception as ex: return jsonify({"success":False,"error":str(ex)}),500

@app.route('/api/admin/login',methods=['POST'])
def alog():
    try:
        d=request.get_json()
        e,pw=d.get('email','').strip().lower(),d.get('password','')
        h=hashlib.sha256(pw.encode()).hexdigest()
        if e==ADMIN_EMAIL and h==ADMIN_HASH: return jsonify({"success":True,"token":ADMIN_HASH,"admin":{"email":e,"name":"المشرف","role":"admin"}})
        if e in usr_db and usr_db[e].get("role")=="admin" and usr_db[e]["ph"]==h: return jsonify({"success":True,"token":usr_db[e]["ph"],"admin":{"email":e,"name":usr_db[e]["name"],"role":"admin"}})
        return jsonify({"success":False,"error":"صلاحيات خاطئة"}),401
    except Exception as ex: return jsonify({"success":False,"error":str(ex)}),500

@app.route('/api/admin/stats',methods=['POST'])
def astats():
    try:
        d=request.get_json()
        if not is_admin(d): return jsonify({"error":"غير مصرح"}),403
        cp=[p for p in pay_db.values() if p.get("s")=="confirmed"]
        rev=sum(p.get("amt",0) for p in cp)
        pc=len([c for c in com_db if c.get("s")=="pending"])
        su,pm={},{}
        for o in opt_db: su[o.get("st","?")]=su.get(o.get("st","?"),0)+1
        for p in cp: pm[p.get("mt","?")]=pm.get(p.get("mt","?"),0)+1
        ro=sorted(opt_db,key=lambda x:x["t"],reverse=True)[:10]
        return jsonify({"success":True,"stats":{"users":len(usr_db),"payments":len(pay_db),"confirmed":len(cp),"revenue":rev,"comments":len(com_db),"pending":pc,"opts":len(opt_db),"svcUse":su,"payMeth":pm},"recent":ro})
    except Exception as ex: return jsonify({"success":False,"error":str(ex)}),500

@app.route('/api/admin/comments',methods=['POST'])
def acom_list():
    try:
        d=request.get_json()
        if not is_admin(d): return jsonify({"success":False,"error":"غير مصرح"}),403
        allc=sorted(com_db,key=lambda x:x["t"],reverse=True)
        return jsonify({"success":True,"comments":allc})
    except Exception as ex: return jsonify({"success":False,"error":str(ex)}),500

@app.route('/api/admin/comments/moderate',methods=['POST'])
def acom_moderate():
    try:
        d=request.get_json()
        if not is_admin(d): return jsonify({"success":False,"error":"غير مصرح"}),403
        cid, action = d.get('id',''), d.get('action','')
        if action not in ('approve','reject'): return jsonify({"success":False,"error":"إجراء غير معروف"}),400
        global com_db
        idx=next((i for i,c in enumerate(com_db) if c.get("id")==cid), None)
        if idx is None: return jsonify({"success":False,"error":"غير موجود"}),404
        if action=='approve':
            com_db[idx]["s"]="approved"
        else:
            com_db.pop(idx)
        save()
        return jsonify({"success":True})
    except Exception as ex: return jsonify({"success":False,"error":str(ex)}),500

if __name__=='__main__':
    os.makedirs('static',exist_ok=True)
    load()
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1'
    print("="*55)
    print("🇩🇿  Opticrowt - Server")
    print("="*55)
    print(f"🚀  Running on port {port}")
    print("👤  admin@intajia.dz / admin123")
    print("="*55)
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
