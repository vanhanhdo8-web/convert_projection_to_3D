// ================================================
// MÔ HÌNH CAD 3D TỪ BẢN VẼ KỸ THUẬT
// Đơn vị: mm
// ================================================

$fn = 100; // Độ mịn cho các mặt cong

// Thông số kích thước chính
total_x = 90;
total_y = 60;
total_z = 50;
base_z  = 20;

// Rãnh đáy dưới (Bottom Groove)
groove_y_start = 15;
groove_y_width = 20;
groove_h       = 5;

// Vách đứng (Back Wall)
wall_thick   = 15;
wall_top_w   = 20;
wall_bot_w   = 60; // từ X=15 đến X=75
wall_slope_h = 15;
hole_dia     = 18;
hole_z       = 35;

// Rãnh khuyết phía trước (Front Cutout)
front_cut_w  = 40;
front_cut_d  = 20;
front_cut_r  = 10;

module object_3d() {
    difference() {
        union() {
            // 1. Khối đế chính (Base block)
            cube([total_x, total_y, base_z]);
            
            // 2. Vách đứng phía sau (Back Upright Wall)
            translate([0, 0, base_z])
                rotate([90, 0, 90])
                    linear_extrude(height = wall_thick)
                        polygon(points = [
                            [0, 0],
                            [total_x, 0],
                            [total_x, 0], 
                            [15 + wall_bot_w, 0],
                            [15 + wall_bot_w, 15],
                            [45 + wall_top_w/2, 30],
                            [45 - wall_top_w/2, 30],
                            [15, 15],
                            [15, 0]
                        ]);
        }
        
        // --- CÁC PHẦN CẮT BỎ (SUBTRACTIONS) ---
        
        // A. Rãnh chạy dọc phía dưới đáy (Bottom Channel along X)
        translate([-1, groove_y_start, -1])
            cube([total_x + 2, groove_y_width, groove_h + 1]);
            
        // B. Lỗ tròn Ø18 trên vách đứng
        translate([total_x/2, -1, hole_z])
            rotate([-90, 0, 0])
                cylinder(d = hole_dia, h = wall_thick + 2);
                
        // C. Khuyết mặt trước (Rõng chữ U + R10)
        translate([(total_x - front_cut_w)/2, total_y - front_cut_d, -1])
            cube([front_cut_w, front_cut_d + 1, base_z + 2]);
            
        translate([total_x/2, total_y - front_cut_d, -1])
            cylinder(r = front_cut_r, h = base_z + 2);
    }
}

// Hiển thị mô hình
object_3d();