// =======================================================
// Dinh nghia cac tham so kich thuoc tu ban ve
// =======================================================
LENGTH = 90;            // Chieu dai tong the (truc X)
WIDTH = 60;             // Chieu rong tong the (truc Y)
HEIGHT_BASE = 15;       // Chieu cao phan de (truc Z)
HEIGHT_UPPER = 40;      // Chieu cao phan tren L-shape (truc Z, tinh tu mat tren cua de)
DEPTH_UPPER = 20;       // Chieu sau cua phan tren L-shape (truc Y)

CYLINDER_DIAMETER = 18; // Duong kinh lo tron
CYLINDER_RADIUS = CYLINDER_DIAMETER / 2;

SEMI_CIRCLE_RADIUS = 20; // Ban kinh ranh ban nguyet
// Tam cua cung ban nguyet theo chieu Z se la: HEIGHT_BASE + HEIGHT_UPPER - SEMI_CIRCLE_RADIUS
// => 15 + 40 - 20 = 35

NOTCH_WIDTH = 20;       // Chieu rong ranh chu nhat
NOTCH_HEIGHT = 20;      // Chieu cao ranh chu nhat

// So do phan giai cho hinh tru (smoother circles)
$fn = 64;

// =======================================================
// Xay dung vat the 3D su dung OpenSCAD
// =======================================================

difference() {
    // 1. Khoi co ban: Gom phan de va phan L-shape phia tren
    union() {
        // Phan de: Khoi chu nhat kich thuoc [90, 60, 15]
        // Vi tri goc dau tien [0,0,0]
        cube([LENGTH, WIDTH, HEIGHT_BASE]);

        // Phan L-shape phia tren: Khoi chu nhat [90, 20, 40]
        // Dat tren cung cua phan de, flush voi canh Y=0
        // Vi tri bat dau cua khoi nay la [0, 0, HEIGHT_BASE]
        translate([0, 0, HEIGHT_BASE]) {
            cube([LENGTH, DEPTH_UPPER, HEIGHT_UPPER]);
        }
    }

    // 2. Cac chi tiet cat (Subtractive Features)

    // A. Lo tron xuyen tam (Diameter 18)
    // Tam lo:
    //   X = LENGTH / 2 = 90 / 2 = 45
    //   Y = WIDTH / 2 = 60 / 2 = 30 (tu hinh chieu bang)
    //   Z = HEIGHT_BASE + HEIGHT_UPPER / 2 = 15 + 40 / 2 = 35 (tu hinh chieu dung)
    translate([LENGTH / 2, WIDTH / 2, HEIGHT_BASE + HEIGHT_UPPER / 2]) {
        // Xoay hinh tru de truc cua no song song voi truc X (chieu dai)
        rotate([0, 90, 0]) {
            // Chieu cao hinh tru (h) lon hon LENGTH mot chut de dam bao cat het
            cylinder(h = LENGTH + 2, r = CYLINDER_RADIUS, center = true);
        }
    }

    // B. Ranh ban nguyet lom o mat truoc cua khoi tren
    // (Mat truoc la mat X-Z, Y=0. Khoi tren co chieu sau DEPTH_UPPER=20)
    // Tam cua cung ban nguyet:
    //   X = WIDTH / 2 = 60 / 2 = 30 (tam cua chieu rong 60mm)
    //   Y = DEPTH_UPPER / 2 = 20 / 2 = 10 (tam de cat xuyen qua chieu sau 20mm)
    //   Z = HEIGHT_BASE + HEIGHT_UPPER - SEMI_CIRCLE_RADIUS = 15 + 40 - 20 = 35
    translate([WIDTH / 2, DEPTH_UPPER / 2, HEIGHT_BASE + HEIGHT_UPPER - SEMI_CIRCLE_RADIUS]) {
        // Cylinder mac dinh truc H la truc Z.
        // Chung ta muon cat theo phuong Y (chieu sau). Vay xoay hinh tru de truc H la truc Y
        rotate([90, 0, 0]) { // Xoay 90 do quanh truc X
            // De tao ranh ban nguyet lom (concave semi-circle), ta can tru di nua phia tren cua hinh tru.
            // Su dung intersection de lay phan nua phia tren cua hinh tru lam dao cat.
            intersection() {
                // Hinh tru co chieu cao (H) lon hon DEPTH_UPPER de dam bao cat het
                cylinder(h = DEPTH_UPPER + 2, r = SEMI_CIRCLE_RADIUS, center = true);
                // Khoi hop de cat bo phan nua duoi, chi giu lai phan nua tren cua hinh tru.
                // Vi hinh tru center=true, nen Z cua no la [-R, R].
                // Chung ta muon giu lai phan Z > 0, nen khoi hop bat dau tu Z=0 len.
                translate([-SEMI_CIRCLE_RADIUS - 1, -DEPTH_UPPER/2 - 1, 0])
                    cube([SEMI_CIRCLE_RADIUS * 2 + 2, DEPTH_UPPER + 2, SEMI_CIRCLE_RADIUS + 1]);
            }
        }
    }

    // C. Ranh chu nhat o mat truoc cua khoi tren
    // (Rong 20, cao 20, sau 20)
    // Vi tri bat dau cua ranh:
    //   X = (WIDTH - NOTCH_WIDTH) / 2 = (60 - 20) / 2 = 20
    //   Y = -1 (cat tu ben ngoai vao de dam bao cat het phan tu Y=0)
    //   Z = HEIGHT_BASE = 15
    translate([(WIDTH - NOTCH_WIDTH) / 2, -1, HEIGHT_BASE]) {
        // Chieu sau cua khoi hop (Y) lon hon DEPTH_UPPER de dam bao cat het
        cube([NOTCH_WIDTH, DEPTH_UPPER + 2, NOTCH_HEIGHT]);
    }
}