// Mô hình 3D từ bản vẽ hình chiếu kỹ thuật
// Kích thước chuẩn theo bản vẽ:
// - Tổng chiều dài (X): 65 mm
// - Tổng chiều rộng (Y): 28 mm
// - Tổng chiều cao (Z): 27 mm

$fn = 80; // Độ mịn đường cong tròn

module chi_tiet_co_khi() {
    difference() {
        // 1. Khối phôi bậc thang cơ sở
        union() {
            // Bậc thấp (bên trái): dài 33, rộng 28, cao 14
            cube([33, 28, 14]);
            
            // Bậc cao (bên phải): dài 32, rộng 28, cao 27
            translate([33, 0, 0])
                cube([32, 28, 27]);
        }
        
        // 2. Lỗ tròn xuyên suốt phi 13 ở bậc thấp
        // Tâm lỗ cách mép trái 20mm, nằm chính giữa bề rộng (y = 14mm)
        translate([20, 14, -1])
            cylinder(d = 13, h = 16);
            
        // 3. Rãnh chữ U ở bậc cao
        // Chiều sâu rãnh: 14mm (từ mép phải x = 65 lùi vào x = 51)
        // Chiều rộng rãnh: 18mm (nằm đối xứng ở giữa, y từ 5 đến 23)
        // Chiều cao: xuyên suốt toàn bộ chiều cao (z từ -1 đến 29)
        translate([65 - 14, (28 - 18) / 2, -1])
            cube([15, 18, 29]);
    }
}

chi_tiet_co_khi();
