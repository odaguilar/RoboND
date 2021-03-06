import numpy as np
import cv2

# Identify pixels above the threshold
# Threshold of RGB > 160 does a nice job of identifying ground pixels only
def color_thresh(img, rgb_thresh=(160, 160, 160)):
    # Create an array of zeros same xy size as img, but single channel
    color_select = np.zeros_like(img[:,:,0])
    # Require that each pixel be above all three threshold values in RGB
    # above_thresh will now contain a boolean array with "True"
    # where threshold was met
    above_thresh = (img[:,:,0] > rgb_thresh[0]) \
                & (img[:,:,1] > rgb_thresh[1]) \
                & (img[:,:,2] > rgb_thresh[2])
    # Index the array of zeros with the boolean array and set to 1
    color_select[above_thresh] = 1
    # Return the binary image
    return color_select

# Identify obstacles
def obstacle_thresh(img, rgb_thresh=(160, 160, 160)):
    # Create an array of zeros same xy size as img, but single channel
    obstacle_select = np.zeros_like(img[:,:,0])
    # Require that each pixel be below all three threshold values in RGB
    # below_thresh will now contain a boolean array with "True"
    # where threshold was met
    below_thresh = (img[:,:,0] < rgb_thresh[0]) \
                & (img[:,:,1] < rgb_thresh[1]) \
                & (img[:,:,2] < rgb_thresh[2])
    # Index the array of zeros with the boolean array and set to 1
    obstacle_select[below_thresh] = 1
    # Return the binary image
    return obstacle_select

def rock_thresh(img, lower_yellow=(100, 100, 0),upper_yellow=(210, 210, 55)): 
    # Threshold the image to get only yellow colors
    mask = cv2.inRange(img, lower_yellow, upper_yellow)
    return mask

# Define a function to convert from image coords to rover coords
def rover_coords(binary_img):
    # Identify nonzero pixels
    ypos, xpos = binary_img.nonzero()
    # Calculate pixel positions with reference to the rover position being at the 
    # center bottom of the image.  
    x_pixel = -(ypos - binary_img.shape[0]).astype(np.float)
    y_pixel = -(xpos - binary_img.shape[1]/2 ).astype(np.float)
    return x_pixel, y_pixel

# Define a function to convert to radial coords in rover space
def to_polar_coords(x_pixel, y_pixel):
    # Convert (x_pixel, y_pixel) to (distance, angle) 
    # in polar coordinates in rover space
    # Calculate distance to each pixel
    dist = np.sqrt(x_pixel**2 + y_pixel**2)
    # Calculate angle away from vertical for each pixel
    angles = np.arctan2(y_pixel, x_pixel)
    return dist, angles

# Define a function to map rover space pixels to world space
def rotate_pix(xpix, ypix, yaw):
    # Convert yaw to radians
    yaw_rad = yaw * np.pi / 180
    xpix_rotated = (xpix * np.cos(yaw_rad)) - (ypix * np.sin(yaw_rad))                       
    ypix_rotated = (xpix * np.sin(yaw_rad)) + (ypix * np.cos(yaw_rad))
    # Return the result  
    return xpix_rotated, ypix_rotated

def translate_pix(xpix_rot, ypix_rot, xpos, ypos, scale): 
    # Apply a scaling and a translation
    xpix_translated = (xpix_rot / scale) + xpos
    ypix_translated = (ypix_rot / scale) + ypos
    # Return the result  
    return xpix_translated, ypix_translated

# Define a function to apply rotation and translation (and clipping)
# Once you define the two functions above this function should work
def pix_to_world(xpix, ypix, xpos, ypos, yaw, world_size, scale):
    # Apply rotation
    xpix_rot, ypix_rot = rotate_pix(xpix, ypix, yaw)
    # Apply translation
    xpix_tran, ypix_tran = translate_pix(xpix_rot, ypix_rot, xpos, ypos, scale)
    # Perform rotation, translation and clipping all at once
    x_pix_world = np.clip(np.int_(xpix_tran), 0, world_size - 1)
    y_pix_world = np.clip(np.int_(ypix_tran), 0, world_size - 1)
    # Return the result
    return x_pix_world, y_pix_world

# Define a function to perform a perspective transform
def perspect_transform(img, src, dst):       
    M = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(img, M, (img.shape[1], img.shape[0]))# keep same size as input image
    mask = cv2.warpPerspective(np.ones_like(img[:,:,0]), M, (img.shape[1], img.shape[0]))
    
    return warped, mask    


# Apply the above functions in succession and update the Rover state accordingly
def perception_step(Rover):
    dst_size = 5 
    bottom_offset = 6
    source = np.float32([[14, 140], [301 ,140],[200, 96], [118, 96]])
    destination = np.float32([
                      [Rover.img.shape[1]/2 - dst_size, Rover.img.shape[0] - bottom_offset],
                      [Rover.img.shape[1]/2 + dst_size, Rover.img.shape[0] - bottom_offset],
                      [Rover.img.shape[1]/2 + dst_size, Rover.img.shape[0] - 2*dst_size - bottom_offset], 
                      [Rover.img.shape[1]/2 - dst_size, Rover.img.shape[0] - 2*dst_size - bottom_offset],
                      ])
    
    # 2) Apply perspective transform
    warped, mask = perspect_transform(Rover.img, source, destination)
    
    # 3) Apply color threshold to identify navigable terrain/obstacles/rock samples  
    obstacles = obstacle_thresh(warped) * mask 
    rocks = rock_thresh(warped)
    navigable = color_thresh(warped)
    
    # 4) Update Rover.vision_image (this will be displayed on left side of screen)     
    Rover.vision_image[:,:,0] = obstacles * 255
    Rover.vision_image[:,:,1] = rocks 
    Rover.vision_image[:,:,2] = navigable * 255

    # 5) Convert map image pixel values to rover-centric coords
    obstacles_x, obstacles_y = rover_coords(obstacles)
    rocks_x, rocks_y = rover_coords(rocks)
    navigable_x, navigable_y = rover_coords(navigable)

    # 6) Convert rover-centric pixel values to world coordinates
    obstacles_x_world, obstacles_y_world = pix_to_world(obstacles_x, obstacles_y, Rover.pos[0], Rover.pos[1], Rover.yaw, world_size=200, scale=10)
    rocks_x_world, rocks_y_world = pix_to_world(rocks_x, rocks_y, Rover.pos[0], Rover.pos[1], Rover.yaw, world_size=200, scale=10)
    navigable_x_world, navigable_y_world = pix_to_world(navigable_x, navigable_y, Rover.pos[0], Rover.pos[1], Rover.yaw, world_size=200, scale=10)

    # 7) Update Rover worldmap (to be displayed on right side of screen)
    rover_velocity = Rover.vel
    rover_steer = Rover.steer
    if rover_velocity >= 0.8:
        if (rover_steer >= -4.0) and (rover_steer <= 4.0):
            Rover.worldmap[obstacles_y_world, obstacles_x_world, 0] += 10
            Rover.worldmap[rocks_y_world, rocks_x_world, 1] += 255
            Rover.worldmap[navigable_y_world, navigable_x_world, 2] += 255

    # 8) Convert rover-centric pixel positions to polar coordinates
    rocks_dist, rocks_angles = to_polar_coords(rocks_x, rocks_y)
    nav_dist, nav_angles = to_polar_coords(navigable_x, navigable_y)

    # Update Rover pixel distances and angles
    Rover.rock_dists = rocks_dist
    Rover.rock_angles = rocks_angles
    Rover.nav_dists = nav_dist
    Rover.nav_angles = nav_angles
    
    return Rover