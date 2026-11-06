// =========================================================
// BAN VE KY THUAT CO KHI - KHOT CANH & LO TRUYEN
// Don vi do: millimeter (mm)
// =========================================================

$fn = 80; // Do min cho cac mat cong

// Thong so kich thuoc chinh
total_x = 90;
total_y = 60;
total_z = 50;
base_z  = 20;

module main_model() {
    difference() {
        // --- 1. KHOI TAO HINH DANG BEN NGOAI ---
        union() {
            // De duoi
            translate([-total_x/2, -total_y/2, 0])
                cube([total_x, total_y, base_z]);
            
            // Than tren khoi thang (Z: 20 -> 35)
            translate([-total_x/2, -total_y/2, base_z])
                cube([total_x, total_y, 15]);
                
            // Than tren khoi vat (Z: 35 -> 50) thu hep tu 90 xuong 20
            hull() {
                translate([-total_x/2, -total_y/2, 35])
                    cube([total_x, total_y, 0.1]);
                translate([-10, -total_y/2, total_z - 0.1])
                    cube([20, total_y, 0.1]);
            }
        }

        // --- 2. CAC CHI TIET KHOET / TRU ---
        // a. Lo tron ngang Phi 18mm
        translate([0, -(total_y/2 + 5), 32])
            rotate([-90, 0, 0])
            cylinder(d=18, h=total_y + 10);

        // b. Ranh cat vuong o khoi tren (Rong 40, Sau 20, Cao 16)
        translate([-20, 10, 34.9])
            cube([40, 21, 16]);

        // c. Lo tru khoet dung R10 (Phi 20) tren ranh
        translate([0, 20, 30])
            cylinder(r=10, h=25);

        // d. Ranh cat ngang theo truc Y (Rong 20, Cao 16)
        translate([-(total_x/2 + 5), -10, 34.9])
            cube([total_x + 10, 20, 16]);
    }
}

// Hien thi mo hinh
main_model();