"""Generates test_cases.csv + design/*.csv (requirement analysis, conditions, scenarios).
Expected results are derived ONLY from the acceptance criteria in the STLab02 Instruction (never from app output)."""
import csv, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
(ROOT / 'design').mkdir(exist_ok=True)

# ---------------------------------------------------------------- requirement analysis
REQS = [
    # id, module, actor, rule, precondition, input/output, risk, clarification
    ('REQ-02', 'Cart', 'Customer', 'quantity la so nguyen duong; cung SKU thi cong don vao 1 dong',
     'Catalog co SKU active', 'In: sku, quantity. Out: cart.lines, subtotal; loi INVALID_QUANTITY',
     'Chap nhan 0/am/so thuc/bool; tach dong trung SKU lam sai subtotal',
     'bool (True) co duoc coi la so nguyen? Co gioi han tren so luong / stock khi add khong?'),
    ('REQ-04', 'Authentication', 'Customer, Guest', 'Chi khach da dang nhap moi checkout duoc',
     'Cart co hang', 'In: customer.authenticated. Out: Order hoac LOGIN_REQUIRED',
     'Guest tao don hoac tru kho truoc khi bi chan', 'Guest bi chan o buoc nao (truoc moi side effect)?'),
    ('REQ-07', 'Promotion', 'Customer', 'Ma khong hop le/da dung bi tu choi; chi danh dau used SAU khi order thanh cong',
     'Customer dang nhap, cart >= 500k', 'In: voucher code. Out: discount hoac INVALID_VOUCHER/VOUCHER_USED; customer.used_codes',
     'Ma bi "dot" khi thanh toan that bai; dung lai ma da dung', 'Ma het han / inactive co ma loi rieng khong?'),
    ('REQ-09', 'Shipping', 'Customer', 'Noi thanh: mien phi neu subtotal >= 500k, nguoc lai 30k; ngoai thanh 50k',
     'Co khu vuc giao hang', 'In: subtotal, area. Out: phi ship',
     'Sai dau >= / > tai 500.000; ngoai thanh bi mien phi', 'Subtotal tinh truoc hay sau giam gia? (code dung truoc giam)'),
    ('REQ-10', 'Payment', 'Customer', 'COD -> PENDING_COD; ONLINE chi PAID khi approved; declined khong tao don',
     'Cart hop le', 'In: method, approved. Out: status, orders, charges',
     'Tao don/charge khi declined; charge sai so tien', 'Declined co can giu lai stock/voucher? (xem REQ-07/08)'),
    ('REQ-12', 'Order', 'System', 'Order ID duy nhat; total = subtotal - discount + shipping; total >= 0',
     'Checkout thanh cong', 'In: cart, voucher, area. Out: Order(order_id,total,discount,shipping)',
     'Trung ID; cong thuc tong sai dau', 'Co truong hop total am nao co the xay ra (discount > subtotal)? Hien tai khong.'),
    ('REQ-14', 'Cart Integrity', 'Customer', 'Gio rong khong checkout duoc',
     'Cart khong co line', 'In: cart rong. Out: EMPTY_CART', 'Tao don 0 dong / charge 0 dong', 'Khong'),
    ('REQ-15', 'Inventory Atomicity', 'System', 'Mot SKU thieu ton kho -> reject ca don, khong tru SKU con lai',
     'Cart nhieu SKU', 'In: lines. Out: OUT_OF_STOCK + stock khong doi', 'Tru kho mot phan roi moi loi (lech ton)',
     'Stock dung bang so luong dat co hop le khong? (co - bien duoi)'),
    ('REQ-16', 'Payment Safety', 'System, API client', 'Phuong thuc ngoai COD/ONLINE phai bi tu choi',
     'Cart hop le', 'In: method. Out: INVALID_PAYMENT_METHOD, khong side effect',
     'Tru kho/dung voucher truoc khi tu choi method sai', 'Co chap nhan "cod" viet thuong? (coi la khong - so khop chinh xac)'),
]

CONDS = {  # cond_id: (req, description, type)
    'COND-CRT-01': ('REQ-02', 'Quantity la so nguyen duong (bien duoi = 1)', 'positive/boundary'),
    'COND-CRT-02': ('REQ-02', 'Quantity khong hop le: 0, am, so thuc, bool', 'negative/boundary'),
    'COND-CRT-03': ('REQ-02', 'Them cung SKU nhieu lan phai cong don', 'positive'),
    'COND-AUT-01': ('REQ-04', 'Khach da dang nhap checkout thanh cong', 'positive'),
    'COND-AUT-02': ('REQ-04', 'Khach chua dang nhap bi tu choi va khong side effect', 'negative'),
    'COND-VOU-01': ('REQ-07', 'Ma khong ton tai bi tu choi', 'negative'),
    'COND-VOU-02': ('REQ-07', 'Ma da dung bi tu choi', 'negative'),
    'COND-VOU-03': ('REQ-07', 'used_codes chi doi khi order thanh cong', 'state'),
    'COND-SHP-01': ('REQ-09', 'Noi thanh tai/tren nguong 500.000 -> 0', 'boundary'),
    'COND-SHP-02': ('REQ-09', 'Noi thanh duoi nguong -> 30.000', 'boundary'),
    'COND-SHP-03': ('REQ-09', 'Ngoai thanh luon 50.000', 'positive'),
    'COND-PAY-01': ('REQ-10', 'COD -> PENDING_COD, khong charge', 'positive'),
    'COND-PAY-02': ('REQ-10', 'ONLINE approved -> PAID, charge dung so tien', 'positive'),
    'COND-PAY-03': ('REQ-10', 'ONLINE declined -> loi, khong tao don/charge', 'negative'),
    'COND-ORD-01': ('REQ-12', 'total = subtotal - discount + shipping', 'positive'),
    'COND-ORD-02': ('REQ-12', 'Order ID khong trung giua cac don', 'positive'),
    'COND-EMP-01': ('REQ-14', 'Gio rong bi tu choi, khong side effect', 'negative'),
    'COND-EMP-02': ('REQ-14', 'Gio co hang checkout binh thuong (doi chung)', 'positive'),
    'COND-ATM-01': ('REQ-15', 'Co SKU thieu ton -> reject ca don, stock khong doi', 'negative'),
    'COND-ATM-02': ('REQ-15', 'So luong dat = stock (bien) duoc chap nhan, +1 bi tu choi', 'boundary'),
    'COND-SAF-01': ('REQ-16', 'Method la WALLET bi tu choi dung loi', 'negative'),
    'COND-SAF-02': ('REQ-16', 'Method sai khong tru kho / khong charge / khong tao don', 'negative/state'),
    'COND-SAF-03': ('REQ-16', 'Method rong bi tu choi', 'negative/boundary'),
}

SCENS = {  # ts_id: (req, description)
    'TS-CRT-01': ('REQ-02', 'Them so luong hop le vao gio'),
    'TS-CRT-02': ('REQ-02', 'Them so luong khong hop le vao gio'),
    'TS-CRT-03': ('REQ-02', 'Them cung SKU hai lan (cong don)'),
    'TS-AUT-01': ('REQ-04', 'Khach dang nhap dat hang'),
    'TS-AUT-02': ('REQ-04', 'Guest co gang dat hang'),
    'TS-VOU-01': ('REQ-07', 'Ap ma khong ton tai'),
    'TS-VOU-02': ('REQ-07', 'Ap lai ma da dung'),
    'TS-VOU-03': ('REQ-07', 'Trang thai used_codes sau thanh cong / sau declined'),
    'TS-SHP-01': ('REQ-09', 'Phi ship noi thanh tai nguong mien phi'),
    'TS-SHP-02': ('REQ-09', 'Phi ship noi thanh duoi nguong (checkout end-to-end)'),
    'TS-SHP-03': ('REQ-09', 'Phi ship ngoai thanh'),
    'TS-PAY-01': ('REQ-10', 'Thanh toan COD'),
    'TS-PAY-02': ('REQ-10', 'Thanh toan ONLINE duoc duyet'),
    'TS-PAY-03': ('REQ-10', 'Thanh toan ONLINE bi tu choi'),
    'TS-ORD-01': ('REQ-12', 'Tinh tong tien cua don'),
    'TS-ORD-02': ('REQ-12', 'Tinh duy nhat cua Order ID'),
    'TS-EMP-01': ('REQ-14', 'Checkout gio rong'),
    'TS-EMP-02': ('REQ-14', 'Checkout gio co hang (control)'),
    'TS-ATM-01': ('REQ-15', 'Dat nhieu SKU, mot SKU thieu ton'),
    'TS-ATM-02': ('REQ-15', 'Dat nhieu SKU, so luong dung bang ton'),
    'TS-SAF-01': ('REQ-16', 'API gui method la WALLET'),
    'TS-SAF-02': ('REQ-16', 'API gui method rong'),
}

P = lambda **k: json.dumps(k, ensure_ascii=False)
PRE = 'Customer U_NEW authenticated; stock A=20,B=15,C=12; fixture moi cho tung case'

# (id, req, cond, ts, title, prio, fixture, input, expected_type, expected)
C = [
 # ---- REQ-02
 ('TC-CRT-001','REQ-02','COND-CRT-01','TS-CRT-01','Them A qty=1 (bien duoi hop le)','P1','empty',P(op='cart_add',adds=[['A',1]]),'value',P(error='',lines=[['A',1]],subtotal='200000')),
 ('TC-CRT-002','REQ-02','COND-CRT-02','TS-CRT-02','Them A qty=0 bi tu choi','P0','empty',P(op='cart_add',adds=[['A',0]]),'error',P(error='INVALID_QUANTITY',lines=[],subtotal='0')),
 ('TC-CRT-003','REQ-02','COND-CRT-02','TS-CRT-02','Them A qty=-1 bi tu choi','P0','empty',P(op='cart_add',adds=[['A',-1]]),'error',P(error='INVALID_QUANTITY',lines=[])),
 ('TC-CRT-004','REQ-02','COND-CRT-02','TS-CRT-02','Them A qty=1.5 (khong nguyen) bi tu choi','P1','empty',P(op='cart_add',adds=[['A',1.5]]),'error',P(error='INVALID_QUANTITY',lines=[])),
 ('TC-CRT-005','REQ-02','COND-CRT-03','TS-CRT-03','Them A qty=2 roi A qty=3 -> 1 dong qty=5','P0','empty',P(op='cart_add',adds=[['A',2],['A',3]]),'value',P(error='',lines=[['A',5]],subtotal='1000000')),
 ('TC-CRT-006','REQ-02','COND-CRT-02','TS-CRT-02','Them A qty=true (bool khong phai so luong nguyen duong)','P2','empty',P(op='cart_add',adds=[['A',True]]),'error',P(error='INVALID_QUANTITY',lines=[])),
 # ---- REQ-04
 ('TC-AUT-001','REQ-04','COND-AUT-01','TS-AUT-01','Khach dang nhap checkout COD','P0','600k',P(op='place',calls=[{}]),'value',P(error='',status='PENDING_COD',orders=1)),
 ('TC-AUT-002','REQ-04','COND-AUT-02','TS-AUT-02','Guest checkout bi LOGIN_REQUIRED, khong don, kho khong doi','P0','unauth_600k',P(op='place',calls=[{}]),'error',P(error='LOGIN_REQUIRED',orders=0,stock_unchanged=True,charges=0)),
 ('TC-AUT-003','REQ-04','COND-AUT-02','TS-AUT-02','Guest + SAVE10 + ONLINE bi chan, voucher khong bi dung','P1','unauth_600k',P(op='place',calls=[{'voucher':'SAVE10','method':'ONLINE'}]),'error',P(error='LOGIN_REQUIRED',orders=0,stock_unchanged=True,charges=0,used_codes=[])),
 # ---- REQ-07
 ('TC-VOU-001','REQ-07','COND-VOU-01','TS-VOU-01','Ma FAKE50 khong ton tai bi INVALID_VOUCHER','P0','600k',P(op='place',calls=[{'voucher':'FAKE50'}]),'error',P(error='INVALID_VOUCHER',orders=0,used_codes=[],stock_unchanged=True)),
 ('TC-VOU-002','REQ-07','COND-VOU-02','TS-VOU-02','Ma SAVE10 da dung bi VOUCHER_USED','P0','used_save10_600k',P(op='place',calls=[{'voucher':'SAVE10'}]),'error',P(error='VOUCHER_USED',orders=0,stock_unchanged=True)),
 ('TC-VOU-003','REQ-07','COND-VOU-03','TS-VOU-03','SAVE10 thanh cong -> used_codes co SAVE10','P1','600k',P(op='place',calls=[{'voucher':'SAVE10'}]),'value',P(error='',discount='60000',used_codes=['SAVE10'],orders=1)),
 ('TC-VOU-004','REQ-07','COND-VOU-03','TS-VOU-03','SAVE10 + ONLINE declined -> used_codes van rong','P0','600k',P(op='place',calls=[{'voucher':'SAVE10','method':'ONLINE','approved':False}]),'error',P(error='PAYMENT_DECLINED',used_codes=[],orders=0)),
 ('TC-VOU-005','REQ-07','COND-VOU-02','TS-VOU-02','Dat 2 don lien tiep cung SAVE10: don 2 bi VOUCHER_USED','P1','600k',P(op='place',calls=[{'voucher':'SAVE10'},{'voucher':'SAVE10'}]),'error',P(errors=['','VOUCHER_USED'],orders=1,used_codes=['SAVE10'])),
 # ---- REQ-09
 ('TC-SHP-001','REQ-09','COND-SHP-02','TS-SHP-01','Noi thanh subtotal 499.999 -> 30.000','P0','empty',P(op='shipping',subtotal='499999',area='inner'),'value',P(error='',fee='30000')),
 ('TC-SHP-002','REQ-09','COND-SHP-01','TS-SHP-01','Noi thanh subtotal 500.000 -> 0 (bien)','P0','empty',P(op='shipping',subtotal='500000',area='inner'),'value',P(error='',fee='0')),
 ('TC-SHP-003','REQ-09','COND-SHP-01','TS-SHP-01','Noi thanh subtotal 500.001 -> 0','P1','empty',P(op='shipping',subtotal='500001',area='inner'),'value',P(error='',fee='0')),
 ('TC-SHP-004','REQ-09','COND-SHP-03','TS-SHP-03','Ngoai thanh 100.000 -> 50.000','P1','empty',P(op='shipping',subtotal='100000',area='outer'),'value',P(error='',fee='50000')),
 ('TC-SHP-005','REQ-09','COND-SHP-03','TS-SHP-03','Ngoai thanh 1.500.000 van 50.000 (khong mien phi)','P0','empty',P(op='shipping',subtotal='1500000',area='outer'),'value',P(error='',fee='50000')),
 ('TC-SHP-006','REQ-09','COND-SHP-02','TS-SHP-02','Checkout 300k noi thanh COD: ship 30.000, total 330.000','P1','300k',P(op='place',calls=[{'area':'inner'}]),'value',P(error='',shipping='30000',total='330000')),
 # ---- REQ-10
 ('TC-PAY-001','REQ-10','COND-PAY-01','TS-PAY-01','COD -> PENDING_COD, khong charge','P0','600k',P(op='place',calls=[{'method':'COD'}]),'value',P(error='',status='PENDING_COD',charges=0,orders=1)),
 ('TC-PAY-002','REQ-10','COND-PAY-02','TS-PAY-02','ONLINE approved -> PAID, 1 charge','P0','600k',P(op='place',calls=[{'method':'ONLINE','approved':True}]),'value',P(error='',status='PAID',charges=1,orders=1)),
 ('TC-PAY-003','REQ-10','COND-PAY-03','TS-PAY-03','ONLINE declined -> loi, khong don, khong charge','P0','600k',P(op='place',calls=[{'method':'ONLINE','approved':False}]),'error',P(error='PAYMENT_DECLINED',orders=0,charges=0)),
 ('TC-PAY-004','REQ-10','COND-PAY-02','TS-PAY-02','ONLINE 600k + SAVE10 charge dung 540.000','P1','600k',P(op='place',calls=[{'method':'ONLINE','approved':True,'voucher':'SAVE10'}]),'value',P(error='',status='PAID',charge_amounts=['540000'])),
 # ---- REQ-12
 ('TC-ORD-001','REQ-12','COND-ORD-01','TS-ORD-01','600k + SAVE10 noi thanh: total = 600000-60000+0','P0','600k',P(op='place',calls=[{'voucher':'SAVE10','area':'inner'}]),'value',P(error='',discount='60000',shipping='0',total='540000')),
 ('TC-ORD-002','REQ-12','COND-ORD-01','TS-ORD-01','300k ngoai thanh khong voucher: total = 300000+50000','P1','300k',P(op='place',calls=[{'area':'outer'}]),'value',P(error='',discount='0',shipping='50000',total='350000')),
 ('TC-ORD-003','REQ-12','COND-ORD-02','TS-ORD-02','Hai don khac key -> hai Order ID khac nhau','P1','600k',P(op='place',calls=[{'key':'K1'},{'key':'K2'}]),'value',P(errors=['',''],orders=2,order_ids_unique=True)),
 # ---- REQ-14
 ('TC-EMP-001','REQ-14','COND-EMP-01','TS-EMP-01','Gio rong -> EMPTY_CART, khong don','P0','empty',P(op='place',calls=[{}]),'error',P(error='EMPTY_CART',orders=0,stock_unchanged=True)),
 ('TC-EMP-002','REQ-14','COND-EMP-01','TS-EMP-01','Gio rong + SAVE10 + ONLINE -> EMPTY_CART, khong charge/voucher','P1','empty',P(op='place',calls=[{'voucher':'SAVE10','method':'ONLINE'}]),'error',P(error='EMPTY_CART',orders=0,charges=0,used_codes=[])),
 ('TC-EMP-003','REQ-14','COND-EMP-02','TS-EMP-02','Gio co 1 san pham B -> checkout duoc (control)','P2','empty',P(op='place',cart=[['B',1]],calls=[{}]),'value',P(error='',orders=1,status='PENDING_COD')),
 # ---- REQ-15
 ('TC-ATM-001','REQ-15','COND-ATM-01','TS-ATM-01','A=2 (du), B=100 (thieu): reject, A khong bi tru','P0','empty',P(op='place',cart=[['A',2],['B',100]],calls=[{}]),'error',P(error='OUT_OF_STOCK',orders=0,stock_unchanged=True)),
 ('TC-ATM-002','REQ-15','COND-ATM-02','TS-ATM-02','A=2, B=16 (ton B=15, vuot 1): reject, kho khong doi','P0','empty',P(op='place',cart=[['A',2],['B',16]],calls=[{}]),'error',P(error='OUT_OF_STOCK',orders=0,stock_unchanged=True)),
 ('TC-ATM-003','REQ-15','COND-ATM-02','TS-ATM-02','A=2, B=15 (dung bang ton): thanh cong, tru dung','P1','empty',P(op='place',cart=[['A',2],['B',15]],calls=[{}]),'value',P(error='',orders=1,stock_delta={'A':-2,'B':-15})),
 ('TC-ATM-004','REQ-15','COND-ATM-01','TS-ATM-01','A=21 (ton 20) dung truoc, B=1 du: reject, B khong bi tru','P1','empty',P(op='place',cart=[['A',21],['B',1]],calls=[{}]),'error',P(error='OUT_OF_STOCK',orders=0,stock_unchanged=True)),
 # ---- REQ-16
 ('TC-SAF-001','REQ-16','COND-SAF-01','TS-SAF-01','method=WALLET -> INVALID_PAYMENT_METHOD, khong don','P0','600k',P(op='place',calls=[{'method':'WALLET'}]),'error',P(error='INVALID_PAYMENT_METHOD',orders=0)),
 ('TC-SAF-002','REQ-16','COND-SAF-02','TS-SAF-01','method=WALLET + SAVE10: khong tru kho, khong charge, voucher chua dung','P0','600k',P(op='place',calls=[{'method':'WALLET','voucher':'SAVE10'}]),'state',P(error='INVALID_PAYMENT_METHOD',orders=0,charges=0,used_codes=[],stock_unchanged=True)),
 ('TC-SAF-003','REQ-16','COND-SAF-03','TS-SAF-02','method="" (rong): bi tu choi va kho khong doi','P1','600k',P(op='place',calls=[{'method':''}]),'state',P(error='INVALID_PAYMENT_METHOD',orders=0,stock_unchanged=True)),
 ('TC-SAF-004','REQ-16','COND-SAF-01','TS-SAF-01','Doi chung COD hop le: kho A giam 3','P2','600k',P(op='place',calls=[{'method':'COD'}]),'value',P(error='',orders=1,stock_delta={'A':-3})),
]

COLS = ['test_case_id','requirement_id','condition_id','scenario_id','title','priority','precondition','fixture_key',
        'input_json','expected_type','expected_json','execution_status','actual_result','error_message','evidence_reference']

with open(ROOT / 'test_cases.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f); w.writerow(COLS)
    for (i, r, c, t, title, pr, fx, inp, et, ex) in C:
        w.writerow([i, r, c, t, title, pr, PRE, fx, inp, et, ex, '', '', '', ''])

with open(ROOT / 'design' / 'requirement_analysis.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f); w.writerow(['requirement_id','module','actor','rule','precondition','input_output','risk','clarification'])
    for r in REQS: w.writerow([r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7]])
with open(ROOT / 'design' / 'conditions.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f); w.writerow(['condition_id','requirement_id','description','type'])
    for k, (r, d, t) in CONDS.items(): w.writerow([k, r, d, t])
with open(ROOT / 'design' / 'scenarios.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f); w.writerow(['scenario_id','requirement_id','description'])
    for k, (r, d) in SCENS.items(): w.writerow([k, r, d])

if __name__ == '__main__':
    neg = sum(1 for c in C if c[8] in ('error', 'state') or 'bien' in c[4])
    print(f'{len(C)} cases | {len(CONDS)} conditions | {len(SCENS)} scenarios | {len(REQS)} REQs | negative/boundary ~{neg}')
