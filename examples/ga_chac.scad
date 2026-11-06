// ================================================
// Gá chạc lỗ tròn
// Đơn vị: mm  (X = dài, Y = rộng, Z = cao)
// Tạo tự động từ dữ liệu hình học của AI
// ================================================

module object_3d() {
    difference() {
        union() {
            translate([0, 0, 0]) cube([65, 28, 12]);
            translate([33, 0, 12]) cube([32, 28, 15]);
        }
        translate([20, 14, -1]) cylinder(r=6.5, h=14, $fn=96);
        translate([51, 5, 12]) cube([15, 18, 16]);
    }
}

object_3d();
